from __future__ import annotations

import threading
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from booksaver.application.browser_executor import InMemorySessionLeaseBroker
from booksaver.application.price_comparison import (
    ArmStatus,
    JevArmRequest,
    JevArmRunner,
    format_comparison_report,
    not_run_arm,
)
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionUsage,
    ObservationSource,
    ObservedOffer,
    ObservedQueryFacts,
    PriceExecutionRequest,
    PriceExecutionResult,
    PriceExecutionStatus,
    RedactedProvenance,
    RefundabilityEvidence,
)
from booksaver.domain.check_result import (
    CheckResult,
    ExtractionMethod,
    RefundIndicators,
)
from booksaver.domain.model_policy import UsdAmount
from booksaver.domain.price_comparison import (
    ArmResult,
    ComparisonArm,
    ComparisonParticipants,
    ComparisonTrigger,
    CostCertainty,
    JevComparisonSettings,
    JevUsage,
    format_usd_nano,
)
from booksaver.domain.user import UserRole
from booksaver.domain.value_objects import Money
from booksaver.infrastructure.persistence.price_comparison import (
    SqlitePriceComparisonRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteCheckHistoryRepository,
    SqliteStore,
    SqliteUserRepository,
)
from tests.support.bookings import seed_booking
from tests.unit.daemon.test_check_coordinator import (
    BrowserContext,
    _build_coordinator,
    _complete_sync,
    _config,
    _seed_session,
    _session_repo,
)
from tests.unit.monitor.fakes import make_booking


class FakeJevExecutor:
    def __init__(self, broker: InMemorySessionLeaseBroker, total: str = "380.00") -> None:
        self.broker = broker
        self.total = total
        self.requests: list[PriceExecutionRequest] = []
        self.restored: list[bytes] = []
        self.last_usage = JevUsage()

    def restore_session(self, data: bytes) -> None:
        self.restored.append(data)

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
        self.requests.append(request)
        self.broker.restore_into(request.session_lease, self)
        self.last_usage = JevUsage(calls=4, input_tokens=2_000, cost_nano_usd=84_000)
        query = request.query
        return PriceExecutionResult(
            PriceExecutionStatus.OBSERVED,
            query_facts=ObservedQueryFacts(
                property_name=query.property_name,
                property_reference=query.property_reference,
                check_in=query.stay_dates.check_in,
                check_out=query.stay_dates.check_out,
                occupancy=query.occupancy,
                currency=query.currency,
                authenticated=True,
                genius=None,
                completeness=EvidenceCompleteness.COMPLETE,
            ),
            offers=(
                ObservedOffer(
                    room_label="Standard Double",
                    total=Money(Decimal(self.total), query.currency),
                    all_in=AllInEvidence.EXPLICIT,
                    refundability=RefundabilityEvidence.EXPLICIT_REFUNDABLE,
                    refundability_text="Free cancellation",
                    completeness=EvidenceCompleteness.COMPLETE,
                ),
            ),
            provenance=RedactedProvenance(ObservationSource.JEV_PRICE_SUBMISSION, 1, 15),
            usage=ExecutionUsage(model_calls=4, total_actions=1, cost=UsdAmount(84)),
        )


def _paired_config(tmp_path: Path, **settings: Any) -> Any:
    return replace(
        _config(tmp_path),
        jev_comparison_settings=JevComparisonSettings(
            enabled=True, participants=ComparisonParticipants.ALL, **settings
        ),
    )


def _baseline_success(booking_id: str) -> CheckResult:
    return CheckResult.success(
        booking_id=booking_id,
        checked_at=datetime.now(UTC),
        live_price=Money(Decimal("390.00"), "EUR"),
        extraction_method=ExtractionMethod.LLM,
        refund_indicators=RefundIndicators(is_refundable=True, raw_text="Free cancellation"),
    )


def _setup(tmp_path: Path, monkeypatch: Any, *, role: UserRole = UserRole.USER) -> Any:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        user = (
            users.get_owner()
            if role is UserRole.OWNER
            else users.get_or_create_by_telegram_id(101, role)
        )
        assert user is not None
        booking = make_booking("00000001-1111-4111-8111-111111111111")
        seed_booking(store, booking, user_id=user.user_id)
    sessions = _session_repo(tmp_path)
    _seed_session(sessions, user.user_id)
    calls: dict[str, list[Any]] = {"pipeline": [], "baseline": []}

    class BaselineMonitor:
        def __init__(self, **kwargs: Any) -> None:
            self.history = kwargs["check_history"]
            self.last_llm_calls_used = 0
            self.last_agentic_outcome = None

        def set_llm_enabled(self, enabled: bool) -> None:
            return None

        def run_authenticated(self, booking: Any, snapshot: Any) -> CheckResult:
            calls["baseline"].append(snapshot.cookies)
            result = _baseline_success(booking.booking_id)
            self.history.add(result)
            return result

    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.BookingComSearchMonitor", BaselineMonitor
    )
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.SavingsPipeline.process",
        lambda _self, results: calls["pipeline"].append(results),
    )
    return user, booking, sessions, calls


def _run(tmp_path: Path, coordinator: Any, user: Any, booking: Any) -> CheckResult:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        result: CheckResult = coordinator._run_booking(store, object(), user.user_id, booking)
    return result


def _arms(tmp_path: Path) -> list[tuple[str, str, str | None, int | None]]:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        rows = store.conn.execute(
            "SELECT arm, status, live_amount, cost_nano_usd FROM price_comparison_arms "
            "ORDER BY arm"
        ).fetchall()
    return [tuple(row) for row in rows]  # type: ignore[misc]


@pytest.mark.parametrize("first", [ComparisonArm.BASELINE, ComparisonArm.JEV])
def test_pair_runs_both_arms_but_only_baseline_owns_canonical_effects(
    tmp_path: Path, monkeypatch: Any, first: ComparisonArm
) -> None:
    user, booking, sessions, calls = _setup(tmp_path, monkeypatch)
    executors: list[FakeJevExecutor] = []
    reports: list[tuple[int, str, str]] = []

    def factory(broker: InMemorySessionLeaseBroker, _cap: int) -> FakeJevExecutor:
        executors.append(FakeJevExecutor(broker))
        return executors[-1]

    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.random.SystemRandom.choice",
        lambda _self, _options: first,
    )
    coordinator = _build_coordinator(
        _paired_config(tmp_path),
        browser_factory=BrowserContext,
        inventory_synchronizer=_complete_sync,
        session_repository=sessions,
        jev_executor_factory=factory,
        comparison_report_sender=lambda u, subject, body: reports.append(
            (u.user_id, subject, body)
        ),
    )

    result = _run(tmp_path, coordinator, user, booking)

    assert result.live_price == Money(Decimal("390.00"), "EUR")
    # Both arms started from the same frozen session snapshot.
    assert len(executors) == 1 and executors[0].restored == calls["baseline"] == [b"[]"]
    # Only the baseline result reaches history and the savings pipeline.
    assert calls["pipeline"] == [[result]]
    with SqliteStore(tmp_path / "booksaver.db") as store:
        history = SqliteCheckHistoryRepository(store).get_recent(booking.booking_id)
        comparison = store.conn.execute(
            "SELECT trigger, first_arm, report_status FROM price_comparisons"
        ).fetchone()
    assert [row.live_price for row in history] == [result.live_price]
    assert tuple(comparison) == ("scheduled", first.value, "sent")
    assert _arms(tmp_path) == [
        ("baseline", "success", "390.00", None),
        ("jev", "success", "380.00", 84_000),
    ]
    [(recipient, subject, body)] = reports
    assert recipient == user.user_id and booking.property.name in subject
    assert "Existing method (Claude): 390.00 EUR · 10.00 EUR below" in body
    assert "Jev (experimental): 380.00 EUR · 20.00 EUR below" in body
    assert "AI cost < $0.0001 · 0s · 4 model calls" in body
    assert "AI cost unknown" in body  # the fake baseline exposes no executor usage
    assert f"{'Jev' if first is ComparisonArm.JEV else 'existing method'} ran first" in body


def test_disabled_or_owner_only_mode_keeps_checks_baseline_only(
    tmp_path: Path, monkeypatch: Any
) -> None:
    user, booking, sessions, calls = _setup(tmp_path, monkeypatch)

    def factory(_broker: InMemorySessionLeaseBroker, _cap: int) -> FakeJevExecutor:
        raise AssertionError("Jev must not run")

    for config in (
        _config(tmp_path),
        replace(
            _config(tmp_path),
            jev_comparison_settings=JevComparisonSettings(enabled=True),  # owner only
        ),
    ):
        coordinator = _build_coordinator(
            config,
            browser_factory=BrowserContext,
            inventory_synchronizer=_complete_sync,
            session_repository=sessions,
            jev_executor_factory=factory,
            comparison_report_sender=lambda *_args: pytest.fail("no report expected"),
        )
        _run(tmp_path, coordinator, user, booking)
    assert len(calls["pipeline"]) == 2
    assert _arms(tmp_path) == []


def test_shutdown_records_jev_as_not_run_and_still_reports(
    tmp_path: Path, monkeypatch: Any
) -> None:
    user, booking, sessions, _calls = _setup(tmp_path, monkeypatch, role=UserRole.OWNER)
    stop = threading.Event()
    reports: list[str] = []
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.random.SystemRandom.choice",
        lambda _self, _options: ComparisonArm.BASELINE,
    )

    coordinator = _build_coordinator(
        _paired_config(tmp_path),
        stop,
        browser_factory=BrowserContext,
        inventory_synchronizer=_complete_sync,
        session_repository=sessions,
        jev_executor_factory=lambda broker, _cap: FakeJevExecutor(broker),
        comparison_report_sender=lambda _u, _s, body: reports.append(body),
    )
    stop.set()
    _run(tmp_path, coordinator, user, booking)
    assert [(arm, status) for arm, status, *_ in _arms(tmp_path)] == [
        ("baseline", "success"),
        ("jev", "not_run"),
    ]
    assert "Jev (experimental): not run — BookSaver was shutting down" in reports[0]


def test_daily_cap_and_short_deadline_become_explicit_not_run_arms() -> None:
    booking = make_booking("b-1")
    runner = JevArmRunner(
        settings=JevComparisonSettings(enabled=True),
        executor_factory=lambda broker, _cap: FakeJevExecutor(broker),
        evaluate=lambda *_args: pytest.fail("must not evaluate"),
    )
    now = datetime.now(UTC)
    capped = runner.run(JevArmRequest(1, booking, b"[]", "rev", now, remaining_daily_nano_usd=0))
    assert (capped.status, capped.outcome_code) == (ArmStatus.NOT_RUN, "daily_cost_limit")
    late = runner.run(JevArmRequest(1, booking, b"[]", "rev", now, remaining_daily_nano_usd=10))
    assert (late.status, late.outcome_code) == (ArmStatus.NOT_RUN, "time_limit")


def test_failure_report_never_claims_no_savings() -> None:
    booking = make_booking("b-1")
    now = datetime.now(UTC)
    baseline = ArmResult(
        arm=ComparisonArm.BASELINE,
        status=ArmStatus.SUCCESS,
        outcome_code="success",
        started_at=now,
        finished_at=now,
        live_price=Money(Decimal("400.00"), "EUR"),
        cost_nano_usd=84_000_000,
        cost_certainty=CostCertainty.EXACT,
    )
    jev = ArmResult(
        arm=ComparisonArm.JEV,
        status=ArmStatus.FAILURE,
        outcome_code="no_equivalent_offer",
        started_at=now,
        finished_at=now,
        cost_nano_usd=12_600,
        cost_certainty=CostCertainty.CONSERVATIVE,
    )
    _subject, body = format_comparison_report(
        booking=booking,
        trigger=ComparisonTrigger.CHECK_NOW,
        comparison_id="abcdef1234",
        first_arm=ComparisonArm.JEV,
        baseline=baseline,
        jev=jev,
    )
    assert "no lower than your booked 400.00 EUR" in body
    assert "Jev (experimental): could not verify a price" in body
    assert "AI cost < $0.0001 (upper bound)" in body and "AI cost $0.084" in body
    assert "no lower" not in body.split("Jev (experimental)")[1]
    assert not_run_arm(ComparisonArm.JEV, "x", "y", now).cost_nano_usd == 0
    assert format_usd_nano(None, CostCertainty.UNKNOWN) == "unknown"


def test_repository_purges_and_closes_interrupted_arms(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        user = users.get_or_create_by_telegram_id(202, UserRole.USER)
        booking = make_booking("00000002-1111-4111-8111-111111111111")
        seed_booking(store, booking, user_id=user.user_id)
        repository = SqlitePriceComparisonRepository(store)
        old = datetime(2026, 9, 1, tzinfo=UTC)
        for comparison_id, created in (("old", old), ("new", datetime.now(UTC))):
            repository.begin(
                comparison_id=comparison_id,
                user_id=user.user_id,
                booking_id=booking.booking_id,
                trigger=ComparisonTrigger.CHECK_NOW,
                cohort="c",
                first_arm=ComparisonArm.JEV,
                now=created,
            )
        statuses = dict(
            store.conn.execute(
                "SELECT comparison_id || ':' || arm, status || ':' || COALESCE(outcome_code, '') "
                "FROM price_comparison_arms"
            ).fetchall()
        )
        assert statuses["old:jev"] == "failure:interrupted"
        assert statuses["new:jev"] == "pending:"
        users.purge(user.user_id)
        assert store.conn.execute("SELECT COUNT(*) FROM price_comparisons").fetchone()[0] == 0
        assert store.conn.execute("SELECT COUNT(*) FROM price_comparison_arms").fetchone()[0] == 0


def _pair_coordinator(tmp_path: Path, sessions: Any, reports: list[str], **extra: Any) -> Any:
    return _build_coordinator(
        _paired_config(tmp_path),
        browser_factory=BrowserContext,
        inventory_synchronizer=_complete_sync,
        session_repository=sessions,
        comparison_report_sender=lambda _u, _s, body: reports.append(body),
        **extra,
    )


def test_comparison_storage_failure_never_changes_the_canonical_check(
    tmp_path: Path, monkeypatch: Any
) -> None:
    user, booking, sessions, calls = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.random.SystemRandom.choice",
        lambda _self, _options: ComparisonArm.JEV,
    )

    def locked(*_args: Any, **_kwargs: Any) -> int:
        raise RuntimeError("database is locked")

    monkeypatch.setattr(SqlitePriceComparisonRepository, "jev_cost_since", locked)
    reports: list[str] = []
    coordinator = _pair_coordinator(
        tmp_path, sessions, reports, jev_executor_factory=lambda b, _c: FakeJevExecutor(b)
    )
    result = _run(tmp_path, coordinator, user, booking)
    assert result.live_price == Money(Decimal("390.00"), "EUR")
    assert calls["pipeline"] == [[result]]
    assert ("jev", "not_run", None, 0) in _arms(tmp_path)
    assert "Jev (experimental): not run" in reports[0]


def test_blocked_baseline_session_skips_the_second_browser(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from booksaver.domain.check_result import FailureCode, FailureReason

    user, booking, sessions, _calls = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.random.SystemRandom.choice",
        lambda _self, _options: ComparisonArm.BASELINE,
    )

    class SignedOutMonitor:
        def __init__(self, **kwargs: Any) -> None:
            self.history = kwargs["check_history"]
            self.last_llm_calls_used = 0
            self.last_agentic_outcome = None

        def set_llm_enabled(self, enabled: bool) -> None:
            return None

        def run_authenticated(self, booking: Any, _snapshot: Any) -> CheckResult:
            result = CheckResult.failure(
                booking.booking_id,
                datetime.now(UTC),
                FailureReason(FailureCode.AUTH_REQUIRED, "signed out"),
            )
            self.history.add(result)
            return result

    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.BookingComSearchMonitor", SignedOutMonitor
    )
    reports: list[str] = []
    coordinator = _pair_coordinator(
        tmp_path,
        sessions,
        reports,
        jev_executor_factory=lambda _b, _c: pytest.fail("Jev must not run"),
    )
    _run(tmp_path, coordinator, user, booking)
    assert ("jev", "not_run", None, 0) in _arms(tmp_path)
    assert "blocked the existing method's session first" in reports[0]


def test_baseline_exception_closes_the_pair_and_still_propagates(
    tmp_path: Path, monkeypatch: Any
) -> None:
    user, booking, sessions, _calls = _setup(tmp_path, monkeypatch)

    class CrashingMonitor:
        def __init__(self, **_kwargs: Any) -> None:
            self.last_llm_calls_used = 0

        def set_llm_enabled(self, enabled: bool) -> None:
            return None

        def run_authenticated(self, *_args: Any) -> CheckResult:
            raise OSError("browser crashed")

    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.BookingComSearchMonitor", CrashingMonitor
    )
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.random.SystemRandom.choice",
        lambda _self, _options: ComparisonArm.BASELINE,
    )
    reports: list[str] = []
    coordinator = _pair_coordinator(
        tmp_path, sessions, reports, jev_executor_factory=lambda b, _c: FakeJevExecutor(b)
    )
    with pytest.raises(OSError):
        _run(tmp_path, coordinator, user, booking)
    assert [(arm, status) for arm, status, *_ in _arms(tmp_path)] == [
        ("baseline", "failure"),
        ("jev", "not_run"),
    ]
    assert reports == []


def test_jev_run_time_is_added_to_the_job_allowance(tmp_path: Path, monkeypatch: Any) -> None:
    from datetime import timedelta

    from booksaver.daemon.check_coordinator import AgenticBrowserJobContext
    from booksaver.domain.model_policy import BrowserJobKind

    user, booking, sessions, _calls = _setup(tmp_path, monkeypatch)
    reports: list[str] = []
    coordinator = _pair_coordinator(
        tmp_path, sessions, reports, jev_executor_factory=lambda b, _c: FakeJevExecutor(b)
    )
    deadline = datetime.now(UTC) + timedelta(seconds=360)
    job = AgenticBrowserJobContext(
        local_user_id=user.user_id,
        job_kind=BrowserJobKind.CHECK_NOW,
        job_id="job-1",
        deadline=deadline,
        job_limit_micro_usd=1_000_000,
        daily_limit_micro_usd=10_000_000,
    )
    coordinator._job_local.agentic = job
    clock = iter(
        [
            datetime(2026, 9, 27, 12, 0, 0, tzinfo=UTC),
            datetime(2026, 9, 27, 12, 0, 42, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(
        "booksaver.application.price_comparison.JevArmRunner.__init__",
        _clocked_runner_init(lambda: next(clock)),
    )
    _run(tmp_path, coordinator, user, booking)
    assert job.deadline == deadline + timedelta(seconds=42)


def _clocked_runner_init(clock: Any) -> Any:
    original = JevArmRunner.__init__

    def init(self: Any, **kwargs: Any) -> None:
        original(self, **kwargs, clock=clock)

    return init


def test_lower_but_non_equivalent_price_is_not_called_no_lower() -> None:
    booking = make_booking("b-1")
    now = datetime.now(UTC)
    jev = ArmResult(
        arm=ComparisonArm.JEV,
        status=ArmStatus.SUCCESS,
        outcome_code="success",
        started_at=now,
        finished_at=now,
        live_price=Money(Decimal("300.00"), "EUR"),
        savings_rejection="room_differs",
        cost_nano_usd=0,
        cost_certainty=CostCertainty.EXACT,
    )
    _subject, body = format_comparison_report(
        booking=booking,
        trigger=ComparisonTrigger.SCHEDULED,
        comparison_id="abc",
        first_arm=ComparisonArm.BASELINE,
        baseline=jev,
        jev=jev,
    )
    assert "not counted as a saving versus your booked 400.00 EUR (room differs)" in body
    assert "no lower" not in body
