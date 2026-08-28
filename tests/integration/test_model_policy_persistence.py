from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

from booksaver.application.async_runner import AsyncLoopRunner
from booksaver.application.model_policy import BrowserJobCostBudget
from booksaver.domain.agent import LLMUsage
from booksaver.domain.model_policy import (
    AdaptiveModelPortfolio,
    BrowserJobKind,
    CallerKeyRef,
    EscalationTrigger,
    ModelAttemptOutcome,
    ModelAttemptPlan,
    ModelCostEstimator,
    ModelRole,
    ModelStopReason,
    QualificationEvaluator,
    QualificationMetrics,
    ReconciliationRequest,
    ReservationRequest,
    ReservationStatus,
    TokenEnvelope,
    UsdAmount,
)
from booksaver.infrastructure.persistence.model_policy import (
    SqliteQualificationRepository,
    SqliteSpendLedger,
    ThreadScopedSqliteSpendLedger,
)
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore, SqliteUserRepository

NOW = datetime(2026, 8, 13, 2, 0, tzinfo=UTC)


def _request(
    *,
    reservation_id: str,
    job_id: str = "job-1",
    ordinal: int = 1,
    cost: int = 100_000,
    job_limit: int = 1_000_000,
    day_limit: int = 10_000_000,
    caller_user_id: int = 1,
):
    profile = AdaptiveModelPortfolio().primary(ModelRole.RECOVERY, "recovery-v1")
    return ReservationRequest(
        reservation_id=reservation_id,
        job_id=job_id,
        job_kind=BrowserJobKind.CHECK_NOW,
        caller_user_id=caller_user_id,
        utc_date=date(2026, 8, 13),
        attempt_ordinal=ordinal,
        profile=profile,
        trigger=EscalationTrigger.INITIAL_AMBIGUOUS,
        reserved_cost=UsdAmount(cost),
        job_limit=UsdAmount(job_limit),
        day_limit=UsdAmount(day_limit),
        preserved_job_allowance=UsdAmount(),
        price_table_version="anthropic-2026-08-12",
        created_at=NOW,
    )


def test_reservation_and_exact_once_reconciliation_survive_reopen(tmp_path) -> None:
    path = tmp_path / "booksaver.db"
    with SqliteStore(path) as store:
        ledger = SqliteSpendLedger(store)
        admitted = ledger.reserve_call(_request(reservation_id="r-1"))
        assert admitted.reservation is not None
        assert admitted.reservation.was_new

    with SqliteStore(path) as store:
        ledger = SqliteSpendLedger(store)
        attempts = ledger.list_attempts("job-1")
        assert len(attempts) == 1
        assert attempts[0].status is ReservationStatus.RESERVED

        reconciled = ledger.reconcile_call(
            ReconciliationRequest(
                reservation_id="r-1",
                charged_cost=UsdAmount(25_000),
                usage=LLMUsage(10_000, 500),
                latency_ms=250,
                outcome=ModelAttemptOutcome.RECOVERED,
                conservative=False,
                completed_at=NOW,
            )
        )
        repeated = ledger.reconcile_call(
            ReconciliationRequest(
                reservation_id="r-1",
                charged_cost=UsdAmount(99_999),
                usage=None,
                latency_ms=999,
                outcome=ModelAttemptOutcome.PROVIDER_FAILED,
                conservative=True,
                completed_at=NOW,
            )
        )
        assert reconciled.charged_cost == UsdAmount(25_000)
        assert repeated.already_reconciled
        assert repeated.charged_cost == UsdAmount(25_000)
        day = store.conn.execute("SELECT * FROM llm_spend_days").fetchone()
        assert day["reserved_micro_usd"] == 0
        assert day["charged_micro_usd"] == 25_000


def test_thread_scoped_ledger_supports_agentic_budget_on_async_runner(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "booksaver.db"
    with SqliteStore(db_path) as store:
        owner = SqliteUserRepository(store).get_owner()

    budget = BrowserJobCostBudget(
        job_id="agentic-thread-boundary",
        job_kind=BrowserJobKind.BOOKINGS_SYNC,
        caller_key_ref=CallerKeyRef(owner.user_id, "shared", "owner_env"),
        ledger=ThreadScopedSqliteSpendLedger(db_path),
        estimator=ModelCostEstimator(),
        preserve_opus_diagnostic=False,
        clock=lambda: NOW,
    )
    plan = ModelAttemptPlan(
        1,
        AdaptiveModelPortfolio().primary(
            ModelRole.EXTRACTION,
            "stagehand-inventory-extract-v1",
        ),
        EscalationTrigger.INITIAL_AMBIGUOUS,
    )

    async def exercise_budget():
        admitted = budget.admit(plan, TokenEnvelope(1_000, 100)).attempt
        assert admitted is not None
        reconciliation = budget.reconcile(
            admitted,
            usage=LLMUsage(400, 20),
            latency_ms=50,
            outcome=ModelAttemptOutcome.COMPLETED,
        )
        return reconciliation, budget.ordered_attempts()

    with AsyncLoopRunner(thread_name="agentic-ledger-regression") as runner:
        reconciliation, attempts = runner.run(exercise_budget(), timeout=5)

    assert reconciliation.status is ReservationStatus.CHARGED
    assert len(attempts) == 1
    assert attempts[0].job_id == "agentic-thread-boundary"
    assert attempts[0].status is ReservationStatus.CHARGED

    with SqliteStore(db_path) as store:
        row = store.conn.execute(
            "SELECT status, outcome FROM llm_cost_reservations WHERE job_id = ?",
            ("agentic-thread-boundary",),
        ).fetchone()
        assert row is not None
        assert tuple(row) == ("charged", "completed")


def test_duplicate_reservation_never_authorizes_a_second_call(tmp_path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        ledger = SqliteSpendLedger(store)
        first = ledger.reserve_call(_request(reservation_id="same"))
        duplicate = ledger.reserve_call(_request(reservation_id="same"))
        assert first.reservation is not None and first.reservation.was_new
        assert duplicate.reservation is not None
        assert duplicate.reservation.was_new is False
        assert store.conn.execute(
            "SELECT COUNT(*) FROM llm_cost_reservations"
        ).fetchone()[0] == 1


def test_multiple_roles_in_one_job_have_one_ordered_attempt_history(tmp_path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        ledger = SqliteSpendLedger(store)
        first = _request(reservation_id="recovery", ordinal=1)
        second = _request(reservation_id="interpretation", ordinal=2)
        second = replace(
            second,
            profile=AdaptiveModelPortfolio().primary(
                ModelRole.INTERPRETATION, "inventory-v1"
            ),
        )
        assert ledger.reserve_call(first).reservation is not None
        assert ledger.reserve_call(second).reservation is not None
        attempts = ledger.list_attempts("job-1")
        assert [(item.ordinal, item.role) for item in attempts] == [
            (1, "recovery"),
            (2, "interpretation"),
        ]


def test_job_and_deployment_caps_deny_before_reservation(tmp_path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        ledger = SqliteSpendLedger(store)
        assert ledger.reserve_call(
            _request(reservation_id="job-a", cost=900_000)
        ).reservation is not None
        job_denied = ledger.reserve_call(
            _request(reservation_id="job-b", ordinal=2, cost=100_001)
        )
        assert job_denied.denied_reason is ModelStopReason.JOB_COST_LIMIT

        daily_denied = ledger.reserve_call(
            _request(
                reservation_id="day-b",
                job_id="other-job",
                cost=150_000,
                day_limit=1_000_000,
            )
        )
        assert daily_denied.denied_reason is ModelStopReason.DAILY_COST_LIMIT
        assert store.conn.execute(
            "SELECT COUNT(*) FROM llm_cost_reservations"
        ).fetchone()[0] == 1


def test_missing_usage_is_conservatively_charged(tmp_path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        ledger = SqliteSpendLedger(store)
        ledger.reserve_call(_request(reservation_id="r-conservative", cost=80_000))
        result = ledger.reconcile_call(
            ReconciliationRequest(
                reservation_id="r-conservative",
                charged_cost=UsdAmount(80_000),
                usage=None,
                latency_ms=20_000,
                outcome=ModelAttemptOutcome.PROVIDER_FAILED,
                conservative=True,
                completed_at=NOW,
            )
        )
        assert result.status is ReservationStatus.CONSERVATIVE
        assert ledger.list_attempts("job-1")[0].usage is None


def test_structurally_returned_model_value_is_persisted_as_completed(tmp_path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        ledger = SqliteSpendLedger(store)
        ledger.reserve_call(_request(reservation_id="r-completed"))
        ledger.reconcile_call(
            ReconciliationRequest(
                reservation_id="r-completed",
                charged_cost=UsdAmount(1_000),
                usage=LLMUsage(400, 20),
                latency_ms=50,
                outcome=ModelAttemptOutcome.COMPLETED,
                conservative=False,
                completed_at=NOW,
            )
        )

        assert ledger.list_attempts("job-1")[0].outcome == "completed"


def test_qualification_is_aggregate_only_and_owner_override_is_audited(tmp_path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        metrics = QualificationMetrics(
            runs=10,
            correct_runs=8,
            diagnosis_runs=10,
            diagnosis_correct_runs=8,
            schema_valid_runs=10,
            prohibited_action_proposals=0,
            prohibited_action_executions=0,
            escalation_count=2,
            total_calls=12,
            total_actions=3,
            input_tokens=1_000,
            output_tokens=100,
            latency_ms=500,
            estimated_cost=UsdAmount(3_000),
        )
        result = QualificationEvaluator().evaluate(
            profile_identity="anthropic:sonnet-opus-v1",
            fixture_version="curated-v1",
            metrics=metrics,
            created_at=NOW,
        )
        repo = SqliteQualificationRepository(store)
        qualification_id = repo.save(result)
        loaded = repo.latest("anthropic:sonnet-opus-v1", "curated-v1")
        assert loaded is not None and not loaded.is_approved
        assert loaded.metrics.total_actions == 3

        owner = SqliteUserRepository(store).get_owner()
        overridden = repo.record_owner_override(
            qualification_id,
            owner_user_id=owner.user_id,
            reason="Reviewed local aggregate replay results",
            overridden_at=NOW,
        )
        assert overridden.is_approved
        columns = {
            row[1]
            for row in store.conn.execute("PRAGMA table_info(llm_profile_qualifications)")
        }
        assert not {"prompt", "page_content", "url", "provider_response"} & columns
