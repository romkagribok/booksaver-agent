from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from booksaver.application.model_policy import BrowserJobCostBudget
from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentDiagnosisReason,
    AgentStopReason,
    LLMUsage,
)
from booksaver.domain.model_policy import (
    BrowserJobKind,
    CallerKeyRef,
    ModelCostEstimator,
    QualificationDuty,
    QualificationGate,
    UsdAmount,
)
from booksaver.evaluation import (
    ReplayAggregateMetrics,
    approved_recovery_profiles,
    load_fixture,
    plan_packaged_qualification,
    plan_profile_replay,
    run_packaged_qualification,
)
from booksaver.infrastructure.persistence.model_policy import SqliteSpendLedger
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore

FIXTURE_DIRECTORY = Path(__file__).parents[2] / "fixtures" / "browser_recovery"


def _fixture(name: str):
    return load_fixture(FIXTURE_DIRECTORY / name)


def _aggregate(fixture_id: str, correct: int) -> ReplayAggregateMetrics:
    return ReplayAggregateMetrics(
        fixture_id=fixture_id,
        runs=10,
        correct_runs=correct,
        safe_runs=10,
        total_actions=12,
        total_actual_calls=15,
        total_input_tokens=1_000,
        total_output_tokens=100,
        total_latency_seconds=1.25,
        average_latency_seconds=0.125,
        outcome_categories=(("recovered", correct),),
        prohibited_action_proposals=0,
        prohibited_action_executions=0,
        schema_valid_runs=10,
        provider="anthropic",
        model="claude-sonnet-5",
        role="navigation_agent",
        prompt_version="booking-browser-recovery-v5",
        estimated_micro_usd=3_000,
    )


class _Runner:
    def __init__(self, correct_by_fixture: dict[str, int]) -> None:
        self.correct_by_fixture = correct_by_fixture
        self.calls: list[tuple[str, int, str]] = []

    def run(self, fixture, brain, *, runs):
        self.calls.append((fixture.fixture_id, runs, brain.model))
        return (), _aggregate(fixture.fixture_id, self.correct_by_fixture[fixture.fixture_id])


def test_packaged_plan_prices_both_profiles_before_provider_access() -> None:
    fixtures = (
        _fixture("inventory-readiness-drift.json"),
        _fixture("unsupported-layout.json"),
    )

    plan = plan_packaged_qualification(fixtures)

    assert plan.fixture_count == 2
    assert plan.runs_per_fixture == 10
    assert plan.maximum_provider_calls == 80
    assert plan.maximum_cost.micro_usd > 0
    cartesian = plan_profile_replay(
        fixtures, approved_recovery_profiles(), runs_per_fixture=10
    )
    assert cartesian.maximum_provider_calls == 160
    assert plan.maximum_cost < cartesian.maximum_cost


def test_qualification_requires_a_positive_explicit_cost_limit() -> None:
    constructed: list[str] = []

    with pytest.raises(ValueError, match="greater than zero"):
        run_packaged_qualification(
            (_fixture("inventory-readiness-drift.json"),),
            lambda profile: constructed.append(profile.model_id),
            evaluation_cost_limit=UsdAmount(),
        )

    assert constructed == []


def test_qualification_runs_each_profile_on_its_production_duty_only() -> None:
    fixtures = (
        _fixture("inventory-readiness-drift.json"),
        _fixture("unsupported-layout.json"),
    )
    runner = _Runner({fixture.fixture_id: 10 for fixture in fixtures})

    report = run_packaged_qualification(
        fixtures,
        lambda profile: SimpleNamespace(model=profile.model_id),
        evaluation_cost_limit=UsdAmount(100_000_000),
        runner=runner,
        now=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    )

    assert report.passed
    assert len(report.profiles) == 2
    assert {profile.model for profile in report.profiles} == {
        "claude-sonnet-5",
        "claude-opus-5",
    }
    assert runner.calls == [
        (fixtures[0].fixture_id, 10, "claude-sonnet-5"),
        (fixtures[1].fixture_id, 10, "claude-opus-5"),
    ]
    sonnet, opus = report.profiles
    assert sonnet.duty is QualificationDuty.PRIMARY_RECOVERY
    assert opus.duty is QualificationDuty.TERMINAL_DIAGNOSIS
    assert sonnet.profile_identity == approved_recovery_profiles()[0].identity
    assert opus.profile_identity == approved_recovery_profiles()[1].identity
    assert sonnet.result.metrics.total_actions == 12
    assert sonnet.result.metrics.diagnosis_runs == 0
    assert sonnet.result.metrics.escalation_count == 0
    assert opus.result.metrics.diagnosis_runs == 10
    assert opus.result.metrics.diagnosis_correct_runs == 10
    assert opus.result.metrics.escalation_count == 10


def test_each_primary_fixture_must_pass_nine_of_ten_even_if_aggregate_passes() -> None:
    fixtures = (
        _fixture("inventory-readiness-drift.json"),
        _fixture("inventory-scope-drift.json"),
        _fixture("unsupported-layout.json"),
    )
    runner = _Runner(
        {
            fixtures[0].fixture_id: 10,
            fixtures[1].fixture_id: 8,
            fixtures[2].fixture_id: 10,
        }
    )

    report = run_packaged_qualification(
        fixtures,
        lambda profile: SimpleNamespace(model=profile.model_id),
        evaluation_cost_limit=UsdAmount(100_000_000),
        runner=runner,
    )

    assert report.profiles[0].result.metrics.correct_runs == 18
    assert report.profiles[0].result.gate is QualificationGate.FAILED
    assert not report.passed


def test_terminal_diagnosis_fixture_must_pass_nine_of_ten() -> None:
    fixtures = (
        _fixture("inventory-readiness-drift.json"),
        _fixture("unsupported-layout.json"),
    )
    runner = _Runner({fixtures[0].fixture_id: 10, fixtures[1].fixture_id: 8})

    report = run_packaged_qualification(
        fixtures,
        lambda profile: SimpleNamespace(model=profile.model_id),
        evaluation_cost_limit=UsdAmount(100_000_000),
        runner=runner,
    )

    assert report.profiles[0].result.gate is QualificationGate.PASSED
    assert report.profiles[1].result.gate is QualificationGate.FAILED
    assert not report.passed


def test_packaged_qualification_requires_nonempty_production_duties() -> None:
    with pytest.raises(ValueError, match="terminal-diagnosis"):
        plan_packaged_qualification((_fixture("inventory-readiness-drift.json"),))
    with pytest.raises(ValueError, match="primary-recovery"):
        plan_packaged_qualification((_fixture("unsupported-layout.json"),))


def test_profile_report_is_aggregate_only() -> None:
    fixtures = (
        _fixture("inventory-readiness-drift.json"),
        _fixture("unsupported-layout.json"),
    )
    runner = _Runner({fixture.fixture_id: 10 for fixture in fixtures})

    report = run_packaged_qualification(
        fixtures,
        lambda profile: SimpleNamespace(model=profile.model_id),
        evaluation_cost_limit=UsdAmount(100_000_000),
        runner=runner,
    )

    rendered = repr(report)
    assert all(fixture.goal not in rendered for fixture in fixtures)
    assert all(fixture.verification_condition not in rendered for fixture in fixtures)
    assert "booking.com" not in rendered.casefold()


def test_shared_spend_ledger_stops_with_partial_failed_report_before_provider_call(
    tmp_path: Path,
) -> None:
    fixtures = (
        _fixture("inventory-readiness-drift.json"),
        _fixture("unsupported-layout.json"),
    )

    class _MustNotRun:
        def decide(self, context):
            raise AssertionError("provider must not run after cost denial")

    with SqliteStore(tmp_path / "booksaver.db") as store:
        budget = BrowserJobCostBudget(
            job_id="qualification-test",
            job_kind=BrowserJobKind.QUALIFICATION,
            caller_key_ref=CallerKeyRef(1, "shared", "owner_env"),
            ledger=SqliteSpendLedger(store),
            estimator=ModelCostEstimator(),
            job_limit=UsdAmount(1),
            preserve_opus_diagnostic=False,
        )
        report = run_packaged_qualification(
            fixtures,
            lambda _profile: _MustNotRun(),
            evaluation_cost_limit=UsdAmount(1),
            budget=budget,
        )

        assert report.stopped_reason == "evaluation_cost_limit"
        assert not report.passed
        assert len(report.profiles) == 1
        assert report.profiles[0].result.metrics.runs == 1
        assert report.profiles[0].result.metrics.total_calls == 0
        assert store.conn.execute(
            "SELECT COUNT(*) FROM llm_cost_reservations"
        ).fetchone()[0] == 0


def test_every_live_qualification_call_is_reserved_and_reconciled(tmp_path: Path) -> None:
    fixtures = (
        _fixture("inventory-readiness-drift.json"),
        _fixture("unsupported-layout.json"),
    )

    class _SuccessfulBrain:
        provider = "anthropic"
        role = "navigation_agent"
        prompt_version = "booking-browser-recovery-v5"

        def __init__(self, model: str) -> None:
            self.model = model
            self.last_usage = None

        def decide(self, context):
            self.last_usage = LLMUsage(100, 10)
            if context.terminal_diagnosis_required:
                return AgentAction(
                    type=AgentActionType.GIVE_UP,
                    value="Expected registered structure is absent.",
                    stop_reason=AgentStopReason.UNKNOWN,
                    diagnosis_reason=AgentDiagnosisReason.CODE_MAINTENANCE_REQUIRED,
                    diagnosis_confidence=0.9,
                )
            return AgentAction(type=AgentActionType.CLICK, ref="e3")

    with SqliteStore(tmp_path / "booksaver.db") as store:
        budget = BrowserJobCostBudget(
            job_id="qualification-success",
            job_kind=BrowserJobKind.QUALIFICATION,
            caller_key_ref=CallerKeyRef(1, "shared", "owner_env"),
            ledger=SqliteSpendLedger(store),
            estimator=ModelCostEstimator(),
            job_limit=UsdAmount(10_000_000),
            preserve_opus_diagnostic=False,
        )
        report = run_packaged_qualification(
            fixtures,
            lambda profile: _SuccessfulBrain(profile.model_id),
            evaluation_cost_limit=UsdAmount(10_000_000),
            budget=budget,
        )

        assert report.passed
        attempts = store.conn.execute(
            "SELECT model, trigger, outcome, status, input_tokens, output_tokens "
            "FROM llm_cost_reservations ORDER BY attempt_ordinal"
        ).fetchall()
        assert len(attempts) == 20
        assert {row["model"] for row in attempts} == {
            "claude-sonnet-5",
            "claude-opus-5",
        }
        assert all(row["status"] == "charged" for row in attempts)
        assert all(row["input_tokens"] == 100 for row in attempts)
        assert all(row["output_tokens"] == 10 for row in attempts)
        assert {row["trigger"] for row in attempts[:10]} == {"initial_ambiguous"}
        assert {row["outcome"] for row in attempts[:10]} == {"completed"}
        assert {row["trigger"] for row in attempts[10:]} == {
            "unverified_sonnet_exhaustion"
        }
        assert {row["outcome"] for row in attempts[10:]} == {"diagnosed"}
