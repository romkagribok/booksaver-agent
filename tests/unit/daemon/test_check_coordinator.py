from __future__ import annotations

import json
import threading
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import MethodType
from typing import Any

import pytest

from booksaver.application.inventory_executor import FakeInventoryBrowserExecutor
from booksaver.application.model_policy import AdaptiveModelSession
from booksaver.application.ports import PageContent
from booksaver.daemon.check_coordinator import (
    AdaptiveBrowserJobContext,
    AgenticBrowserJobContext,
    CheckCoordinator,
    ImmediateAdmission,
    ImmediateCompletion,
    ImmediateCompletionKind,
    InventoryCompletion,
)
from booksaver.domain.account_sync import (
    InventoryCompleteness,
    InventoryDiscoveryResult,
    InventoryRecoveryOutcome,
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationFailureCode,
    SynchronizationReport,
    SynchronizationTrigger,
)
from booksaver.domain.agent import (
    AgentSettings,
    CheckTrace,
    ElementInfo,
    Observation,
    TraceEvent,
    TraceKind,
)
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionRoutingMode,
    ExecutionUsage,
    ObservationSource,
    RedactedProvenance,
    RefundabilityEvidence,
)
from booksaver.domain.browser_resilience import (
    DiagnosisProvenance,
    DomStepId,
    OperatorAction,
    TerminalBrowserDiagnosis,
    TerminalBrowserReason,
)
from booksaver.domain.check_result import (
    CheckResult,
    ExtractionMethod,
    FailureCode,
    FailureReason,
)
from booksaver.domain.errors import UserKeyInvalidError
from booksaver.domain.inventory_executor import (
    InventoryExecutionResult,
    InventoryExecutionStatus,
    InventoryScope,
    ObservedInventoryScope,
    ObservedReservation,
)
from booksaver.domain.model_policy import (
    BrowserJobKind,
    CallerKeyRef,
    ModelAttemptAudit,
    ModelRole,
    ReservationStatus,
    TokenEnvelope,
    UsdAmount,
)
from booksaver.domain.models import Config
from booksaver.domain.schedule import (
    ScheduledAdmission,
    ScheduledCheckSlot,
    ScheduleSettings,
    SlotIdentity,
    SlotStatus,
)
from booksaver.domain.user import UserAccessState, UserRole
from booksaver.domain.user_session import UserSessionMetadata, UserSessionSnapshot
from booksaver.domain.value_objects import (
    CheckInterval,
    DataDirectory,
    LimitsSettings,
    Money,
    NotificationSettings,
    Occupancy,
    Platform,
)
from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)
from booksaver.infrastructure.persistence.scheduled_check_slots import (
    SqliteScheduledCheckSlotRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAccountReservationRepository,
    SqliteAgenticDisclosureConsentRepository,
    SqliteBookingRepository,
    SqliteCheckHistoryRepository,
    SqliteCheckTraceRepository,
    SqliteSavingsRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.monitor.user_limits import DailyCounter, build_check_plan
from tests.unit.monitor.fakes import FakeInteractiveBrowser, make_booking


class BrowserContext(AbstractContextManager[object]):
    def __enter__(self) -> object:
        return object()

    def __exit__(self, *args: object) -> None:
        return None


class ExistingBrowserContext(AbstractContextManager[Any]):
    def __init__(self, browser: Any) -> None:
        self.browser = browser

    def __enter__(self) -> Any:
        return self.browser

    def __exit__(self, *args: object) -> None:
        return None


class NullLLMFactory:
    def for_booking(self, booking: Any) -> None:
        return None

    def agent_brain_for_booking(self, booking: Any) -> None:
        return None


_TEST_SESSION_KEY = "wGeBQ1NevJlDl9nkMrKT4uh90w2yK8sBgKYrp4r1pTk="


def _complete_sync(
    _store: SqliteStore, _browser: Any, _user_id: int, _trigger: Any
) -> SynchronizationReport:
    return SynchronizationReport(
        run_id="test-sync",
        completeness=InventoryCompleteness.COMPLETE,
        discovered=0,
        eligible=0,
        ineligible=0,
    )


def _session_repo(tmp_path: Path) -> EncryptedUserSessionRepository:
    return EncryptedUserSessionRepository(
        DataDirectory(tmp_path), FernetKeyStore(_TEST_SESSION_KEY)
    )


def _seed_session(repo: EncryptedUserSessionRepository, user_id: int) -> None:
    repo.save(
        UserSessionSnapshot(
            metadata=UserSessionMetadata.imported(
                owner_user_id=user_id,
                platform=Platform.BOOKING_COM,
                imported_at=datetime.now(UTC),
                expires_at=None,
            ),
            cookies=b"[]",
        )
    )


def _config(tmp_path: Path, *, checks: int = 3, llm_calls: int = 5) -> Config:
    return Config(
        check_interval=CheckInterval.parse("12h"),
        data_directory=DataDirectory(tmp_path),
        notification_settings=NotificationSettings(),
        loaded_at=datetime.now(UTC),
        agent_settings=AgentSettings(max_llm_calls=4),
        limits_settings=LimitsSettings(
            max_checks_per_user_per_day=checks,
            max_llm_calls_per_user_per_day=llm_calls,
        ),
    )


def _coordinator(
    tmp_path: Path,
    *,
    checks: int = 3,
    llm_calls: int = 5,
    check_counter: DailyCounter | None = None,
    llm_counter: DailyCounter | None = None,
) -> CheckCoordinator:
    return CheckCoordinator(
        _config(tmp_path, checks=checks, llm_calls=llm_calls),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
        inventory_synchronizer=_complete_sync,
        checks_today=check_counter,
        llm_calls_today=llm_counter,
    )


def _add(tmp_path: Path, telegram_id: int, count: int = 1) -> tuple[int, list[Any]]:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(telegram_id, UserRole.USER)
        bookings = [
            make_booking(f"{index:08d}-1111-4111-8111-111111111111")
            for index in range(1, count + 1)
        ]
        for booking in bookings:
            SqliteBookingRepository(store).add(booking, user_id=user.user_id)
    return user.user_id, bookings


def _failure(booking_id: str) -> CheckResult:
    return CheckResult.failure(
        booking_id,
        datetime.now(UTC),
        FailureReason(FailureCode.STEP_FAILED, "test failure"),
    )


def _scheduled_slot(tmp_path: Path, user_id: int, planned_at: datetime) -> SlotIdentity:
    slot = ScheduledCheckSlot(
        identity=SlotIdentity(user_id, planned_at.date(), 0),
        planned_at=planned_at,
    )
    with SqliteStore(tmp_path / "booksaver.db") as store:
        return SqliteScheduledCheckSlotRepository(store).insert_daily_schedule((slot,))[0].identity


def _observed_inventory_reservation(booking: Any, remote_id: str) -> ObservedReservation:
    return ObservedReservation(
        remote_id=remote_id,
        identity_evidence=EvidenceCompleteness.COMPLETE,
        scope=InventoryScope.UPCOMING,
        lifecycle=ReservationLifecycle.UPCOMING,
        confirmation_id=booking.confirmation_id.value,
        property_name=booking.property.name,
        property_reference=booking.property.booking_com_ref,
        check_in=booking.stay_dates.check_in,
        check_out=booking.stay_dates.check_out,
        room_type=booking.room_type.label,
        booked_total=booking.baseline_price,
        all_in=AllInEvidence.EXPLICIT,
        refundability=RefundabilityEvidence.EXPLICIT_REFUNDABLE,
        refundability_text=booking.refundability.note,
        refund_deadline=booking.refundability.deadline,
        occupancy=booking.occupancy,
        completeness=EvidenceCompleteness.COMPLETE,
    )


def _agentic_inventory_result(
    reservations: tuple[ObservedReservation, ...] = (),
    *,
    usage: ExecutionUsage = ExecutionUsage(),
) -> InventoryExecutionResult:
    scopes = tuple(
        ObservedInventoryScope(
            scope=scope,
            requested_scope_visible=True,
            explicit_empty=not any(item.scope is scope for item in reservations),
            pagination_exhausted=True,
            pages_observed=1,
            visible_reservation_count=sum(item.scope is scope for item in reservations),
            detail_count=sum(item.scope is scope for item in reservations),
            completeness=EvidenceCompleteness.COMPLETE,
        )
        for scope in InventoryScope
    )
    return InventoryExecutionResult(
        status=InventoryExecutionStatus.OBSERVED,
        authenticated=True,
        scopes=scopes,
        reservations=reservations,
        provenance=RedactedProvenance(
            source=ObservationSource.FAKE,
            action_count=usage.total_actions,
            evidence_item_count=len(scopes) + len(reservations),
            schema_version="inventory-observation-v1",
        ),
        usage=usage,
        latency_ms=25,
    )


def _seed_inventory_projection(
    tmp_path: Path,
    *,
    user_id: int,
    remote_id: str,
    booking: Any,
) -> str:
    observed_at = datetime.now(UTC)
    observation = ReservationObservation(
        remote_id=remote_id,
        lifecycle=ReservationLifecycle.UPCOMING,
        observed_at=observed_at,
        confirmation_id=booking.confirmation_id.value,
        property_name=booking.property.name,
        property_ref=booking.property.booking_com_ref,
        check_in=booking.stay_dates.check_in,
        check_out=booking.stay_dates.check_out,
        room_type=booking.room_type.label,
        booked_total=booking.baseline_price,
        refundable=True,
        refund_note=booking.refundability.note,
        refund_deadline=booking.refundability.deadline,
        occupancy=booking.occupancy,
    )
    with SqliteStore(tmp_path / "booksaver.db") as store:
        repository = SqliteAccountReservationRepository(store)
        repository.reconcile(
            user_id=user_id,
            run_id=f"seed-{remote_id}",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="seed-session",
            result=InventoryDiscoveryResult(
                observations=(observation,),
                completeness=InventoryCompleteness.INCOMPLETE,
            ),
            observed_at=observed_at,
        )
        reservation = next(
            item
            for item in repository.list_for_user(user_id)
            if item.observation.confirmation_id == booking.confirmation_id.value
        )
    assert reservation.monitoring_booking_id is not None
    return reservation.monitoring_booking_id


def test_scheduled_slot_is_not_claimed_until_shared_gate_is_available(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    user_id, _bookings = _add(tmp_path, 101)
    planned_at = datetime.now(UTC)
    identity = _scheduled_slot(tmp_path, user_id, planned_at)

    coordinator._execution_gate.acquire()  # noqa: SLF001
    try:
        admission = coordinator.run_scheduled_slot(
            identity,
            ScheduleSettings(),
            planned_at,
        )
    finally:
        coordinator._execution_gate.release()  # noqa: SLF001

    assert admission is ScheduledAdmission.BUSY
    with SqliteStore(tmp_path / "booksaver.db") as store:
        persisted = SqliteScheduledCheckSlotRepository(store).list_for_user_date(
            user_id, planned_at.date()
        )[0]
    assert persisted.status is SlotStatus.PLANNED


def test_scheduled_slot_runs_only_its_user_and_completes_durably(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path, checks=10)
    selected_user_id, selected_bookings = _add(tmp_path, 101, count=2)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        foreign_user_id = (
            SqliteUserRepository(store).get_or_create_by_telegram_id(202, UserRole.USER).user_id
        )
        foreign_bookings = [make_booking("99999999-1111-4111-8111-111111111111")]
        SqliteBookingRepository(store).add(foreign_bookings[0], user_id=foreign_user_id)
    planned_at = datetime.now(UTC) - timedelta(seconds=1)
    identity = _scheduled_slot(tmp_path, selected_user_id, planned_at)
    ran: list[str] = []

    def fake_run(self: Any, store: Any, browser: Any, owner: int, booking: Any) -> Any:
        ran.append(booking.booking_id)
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(fake_run, coordinator)  # type: ignore[method-assign]

    admission = coordinator.run_scheduled_slot(
        identity,
        ScheduleSettings(),
        datetime.now(UTC),
    )

    assert admission is ScheduledAdmission.COMPLETED
    assert set(ran) == {booking.booking_id for booking in selected_bookings}
    assert foreign_bookings[0].booking_id not in ran
    with SqliteStore(tmp_path / "booksaver.db") as store:
        persisted = SqliteScheduledCheckSlotRepository(store).list_for_user_date(
            selected_user_id, planned_at.date()
        )[0]
    assert persisted.status is SlotStatus.COMPLETED


def test_check_now_shares_one_lazy_adaptive_job_across_sync_and_search(
    tmp_path: Path,
) -> None:
    runtime = object()
    budgets: list[Any] = []

    class AdaptiveFactory:
        def caller_key_ref_for_user(self, user_id: int) -> CallerKeyRef:
            return CallerKeyRef(user_id, "shared", "owner_env")

        def adaptive_runtime_for_user(self, _user_id: int, budget: Any) -> object:
            budgets.append(budget)
            return runtime

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: AdaptiveFactory(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
    )
    _user_id, bookings = _add(tmp_path, 101)
    seen: list[Any] = []
    completed = threading.Event()

    def fake_sync(
        self: CheckCoordinator,
        _store: Any,
        _browser: Any,
        _owner: int,
        _trigger: Any,
    ) -> SynchronizationReport:
        seen.append(self._current_adaptive_job().runtime)  # noqa: SLF001
        return _complete_sync(_store, _browser, _owner, _trigger)

    def fake_run(
        self: CheckCoordinator,
        _store: Any,
        _browser: Any,
        _owner: int,
        booking: Any,
    ) -> CheckResult:
        seen.append(self._current_adaptive_job().runtime)  # noqa: SLF001
        return _failure(booking.booking_id)

    coordinator._synchronize_user = MethodType(fake_sync, coordinator)  # type: ignore[method-assign]
    coordinator._run_booking = MethodType(fake_run, coordinator)  # type: ignore[method-assign]

    assert (
        coordinator.request_immediate(
            101,
            bookings[0].booking_id,
            lambda _outcome: completed.set(),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert seen == [runtime, runtime]
    assert len(budgets) == 1
    assert budgets[0].job_kind is BrowserJobKind.CHECK_NOW
    assert coordinator.llm_calls_today == {}
    with SqliteStore(tmp_path / "booksaver.db") as store:
        rows = store.conn.execute("SELECT COUNT(*) FROM llm_cost_reservations").fetchone()[0]
    assert rows == 0


def test_adaptive_job_charges_legacy_counter_for_each_physical_reservation(
    tmp_path: Path,
) -> None:
    calls = DailyCounter()

    class AdaptiveFactory:
        def caller_key_ref_for_user(self, user_id: int) -> CallerKeyRef:
            return CallerKeyRef(user_id, "shared", "owner_env")

        def adaptive_runtime_for_user(self, _user_id: int, _budget: Any) -> object:
            return object()

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: AdaptiveFactory(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        llm_calls_today=calls,
    )
    user_id, _bookings = _add(tmp_path, 101)

    with SqliteStore(tmp_path / "booksaver.db") as store:
        context = coordinator._build_adaptive_job_context(  # noqa: SLF001
            store,
            user_id,
            BrowserJobKind.BOOKINGS_SYNC,
        )
        assert context is not None
        first = AdaptiveModelSession(
            role=ModelRole.INTERPRETATION,
            prompt_version="inventory-test-v1",
            budget=context.budget,
        ).start(TokenEnvelope(1, 1))
        second = AdaptiveModelSession(
            role=ModelRole.RECOVERY,
            prompt_version="recovery-test-v1",
            budget=context.budget,
        ).start(TokenEnvelope(1, 1))

    assert first.attempt is not None
    assert second.attempt is not None
    assert calls.count(user_id) == 2


def test_agentic_follow_on_shares_outer_job_cap_but_uses_owner_env_provenance(
    tmp_path: Path,
) -> None:
    class AdaptiveFactory:
        def caller_key_ref_for_user(self, user_id: int) -> CallerKeyRef:
            return CallerKeyRef(user_id, "personal", "encrypted_user_key")

        def adaptive_runtime_for_user(self, _user_id: int, _budget: Any) -> object:
            return object()

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: AdaptiveFactory(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
    )
    user_id, _bookings = _add(tmp_path, 101)

    with SqliteStore(tmp_path / "booksaver.db") as store:
        context = coordinator._build_adaptive_job_context(  # noqa: SLF001
            store,
            user_id,
            BrowserJobKind.CHECK_NOW,
        )
        assert context is not None
        first = AdaptiveModelSession(
            role=ModelRole.INTERPRETATION,
            prompt_version="inventory-test-v1",
            budget=context.budget,
        ).start(TokenEnvelope(1, 1))
        assert first.attempt is not None

        agentic_budget = coordinator._build_agentic_cost_budget(  # noqa: SLF001
            store,
            user_id,
            BrowserJobKind.CHECK_NOW,
            shared_job_id=context.budget.job_id,
        )
        second = AdaptiveModelSession(
            role=ModelRole.RECOVERY,
            prompt_version="agentic-test-v1",
            budget=agentic_budget,
        ).start(TokenEnvelope(1, 1))
        rows = store.conn.execute(
            "SELECT job_id, attempt_ordinal FROM llm_cost_reservations "
            "ORDER BY attempt_ordinal"
        ).fetchall()

    assert second.attempt is not None
    assert agentic_budget.caller_key_ref == CallerKeyRef(user_id, "shared", "owner_env")
    assert [(row["job_id"], row["attempt_ordinal"]) for row in rows] == [
        (context.budget.job_id, 1),
        (context.budget.job_id, 2),
    ]


def test_adaptive_follow_on_reuses_agentic_inventory_job_and_next_ordinal(
    tmp_path: Path,
) -> None:
    class AdaptiveFactory:
        def caller_key_ref_for_user(self, user_id: int) -> CallerKeyRef:
            return CallerKeyRef(user_id, "shared", "owner_env")

        def adaptive_runtime_for_user(self, _user_id: int, _budget: Any) -> object:
            return object()

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: AdaptiveFactory(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
    )
    user_id, _bookings = _add(tmp_path, 101)

    with SqliteStore(tmp_path / "booksaver.db") as store:
        agentic_budget = coordinator._build_agentic_cost_budget(  # noqa: SLF001
            store,
            user_id,
            BrowserJobKind.CHECK_NOW,
        )
        first = AdaptiveModelSession(
            role=ModelRole.EXTRACTION,
            prompt_version="agentic-inventory-test-v1",
            budget=agentic_budget,
        ).start(TokenEnvelope(1, 1))
        assert first.attempt is not None

        adaptive = coordinator._build_adaptive_job_context(  # noqa: SLF001
            store,
            user_id,
            BrowserJobKind.CHECK_NOW,
            shared_job_id=agentic_budget.job_id,
        )
        assert adaptive is not None
        second = AdaptiveModelSession(
            role=ModelRole.RECOVERY,
            prompt_version="legacy-price-test-v1",
            budget=adaptive.budget,
        ).start(TokenEnvelope(1, 1))
        rows = store.conn.execute(
            "SELECT job_id, attempt_ordinal FROM llm_cost_reservations "
            "ORDER BY attempt_ordinal"
        ).fetchall()

    assert second.attempt is not None
    assert adaptive.budget.job_id == agentic_budget.job_id
    assert [(row["job_id"], row["attempt_ordinal"]) for row in rows] == [
        (agentic_budget.job_id, 1),
        (agentic_budget.job_id, 2),
    ]


def test_scheduled_slot_terminalizes_after_unexpected_check_failure(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    user_id, _bookings = _add(tmp_path, 101)
    planned_at = datetime.now(UTC) - timedelta(seconds=1)
    identity = _scheduled_slot(tmp_path, user_id, planned_at)

    def fail_run(self: Any, store: Any, browser: Any, owner: int, booking: Any) -> Any:
        store.conn.execute(
            "UPDATE users SET access_state = access_state WHERE user_id = ?", (owner,)
        )
        raise RuntimeError("unexpected check failure")

    coordinator._run_booking = MethodType(fail_run, coordinator)  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="unexpected check failure"):
        coordinator.run_scheduled_slot(
            identity,
            ScheduleSettings(),
            datetime.now(UTC),
        )

    with SqliteStore(tmp_path / "booksaver.db") as store:
        persisted = SqliteScheduledCheckSlotRepository(store).list_for_user_date(
            user_id, planned_at.date()
        )[0]
    assert persisted.status is SlotStatus.COMPLETED


def test_immediate_check_runs_in_background_and_shares_global_gate(tmp_path: Path) -> None:
    coordinator = _coordinator(tmp_path)
    user_id, bookings = _add(tmp_path, 101)
    entered, release, completed = threading.Event(), threading.Event(), threading.Event()
    outcomes: list[ImmediateCompletion] = []

    def fake_run(self: Any, store: Any, browser: Any, owner: int, booking: Any) -> Any:
        entered.set()
        release.wait(2)
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(fake_run, coordinator)  # type: ignore[method-assign]
    admission = coordinator.request_immediate(
        101, bookings[0].booking_id, lambda outcome: (outcomes.append(outcome), completed.set())
    )
    assert admission is ImmediateAdmission.ACCEPTED
    assert entered.wait(1)

    assert (
        coordinator.request_immediate(101, bookings[0].booking_id, lambda _outcome: None)
        is ImmediateAdmission.BUSY
    )
    coordinator.run_scheduled()  # non-blocking skip while the manual worker owns the gate
    release.set()
    assert completed.wait(1)

    assert outcomes[0].kind is ImmediateCompletionKind.RESULT
    assert coordinator.checks_today == {user_id: 1}


def test_worker_reauthorizes_and_refuses_foreign_booking_without_count(tmp_path: Path) -> None:
    coordinator = _coordinator(tmp_path)
    _owner_id, bookings = _add(tmp_path, 202)
    completed = threading.Event()
    outcomes: list[ImmediateCompletion] = []

    assert (
        coordinator.request_immediate(
            101,
            bookings[0].booking_id,
            lambda outcome: (outcomes.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert outcomes == [ImmediateCompletion(ImmediateCompletionKind.UNAVAILABLE)]
    assert coordinator.checks_today == {}


def test_immediate_check_reports_scoped_auth_required_when_session_is_missing(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    _user_id, bookings = _add(tmp_path, 101)
    completed = threading.Event()
    outcomes: list[ImmediateCompletion] = []

    assert (
        coordinator.request_immediate(
            101,
            bookings[0].booking_id,
            lambda outcome: (outcomes.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    result = outcomes[0].result
    assert result is not None and result.failure_reason is not None
    assert result.failure_reason.code is FailureCode.AUTH_REQUIRED
    assert "--telegram-user-id 101" in result.failure_reason.detail


def test_completion_rechecks_booking_after_long_running_check(tmp_path: Path) -> None:
    coordinator = _coordinator(tmp_path)
    _user_id, bookings = _add(tmp_path, 101)
    completed = threading.Event()
    outcomes: list[ImmediateCompletion] = []

    def delete_during_run(self: Any, store: Any, browser: Any, owner: int, booking: Any) -> Any:
        SqliteBookingRepository(store).delete(booking.booking_id)
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(  # type: ignore[method-assign]
        delete_during_run, coordinator
    )
    coordinator.request_immediate(
        101,
        bookings[0].booking_id,
        lambda outcome: (outcomes.append(outcome), completed.set()),
    )
    assert completed.wait(1)

    assert outcomes == [ImmediateCompletion(ImmediateCompletionKind.UNAVAILABLE)]


def test_manual_daily_limit_persists_failure_without_opening_browser(tmp_path: Path) -> None:
    counter = DailyCounter()
    coordinator = _coordinator(tmp_path, checks=1, check_counter=counter)
    user_id, bookings = _add(tmp_path, 101)
    counter.increment(user_id)
    completed = threading.Event()
    outcomes: list[ImmediateCompletion] = []

    coordinator.request_immediate(
        101,
        bookings[0].booking_id,
        lambda outcome: (outcomes.append(outcome), completed.set()),
    )
    assert completed.wait(1)

    result = outcomes[0].result
    assert result is not None
    assert result.failure_reason is not None
    assert result.failure_reason.code is FailureCode.USER_CHECK_LIMIT_REACHED
    with SqliteStore(tmp_path / "booksaver.db") as store:
        history = SqliteCheckHistoryRepository(store).get_recent(bookings[0].booking_id)
    assert history[0].failure_reason.code is FailureCode.USER_CHECK_LIMIT_REACHED


def test_scheduled_plan_honors_remaining_quota_and_records_only_skipped(
    tmp_path: Path,
) -> None:
    counter = DailyCounter()
    coordinator = _coordinator(tmp_path, checks=2, check_counter=counter)
    user_id, bookings = _add(tmp_path, 101, count=3)
    counter.increment(user_id)
    ran: list[str] = []

    def fake_run(self: Any, store: Any, browser: Any, owner: int, booking: Any) -> Any:
        ran.append(booking.booking_id)
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(fake_run, coordinator)  # type: ignore[method-assign]
    coordinator.run_scheduled()

    assert len(ran) == 1
    assert coordinator.checks_today[user_id] == 2
    with SqliteStore(tmp_path / "booksaver.db") as store:
        history = SqliteCheckHistoryRepository(store)
        skipped = sum(len(history.get_recent(booking.booking_id)) for booking in bookings)
    assert skipped == 2


def test_scheduled_checks_use_a_fresh_browser_context_per_booking(tmp_path: Path) -> None:
    created: list[object] = []
    closed: list[object] = []

    class FreshBrowserContext(AbstractContextManager[object]):
        def __enter__(self) -> object:
            browser = object()
            created.append(browser)
            return browser

        def __exit__(self, *args: object) -> None:
            closed.append(created[-1])

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=FreshBrowserContext,
        inventory_synchronizer=_complete_sync,
    )
    _user_id, bookings = _add(tmp_path, 101, count=2)
    observed: list[object] = []

    def fake_run(self: Any, store: Any, browser: Any, owner: int, booking: Any) -> Any:
        observed.append(browser)
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(fake_run, coordinator)  # type: ignore[method-assign]

    coordinator.run_scheduled()

    assert len(observed) == len(bookings) == 2
    assert observed[0] is not observed[1]
    assert len(created) == len(closed) == 3


def test_missing_user_session_fails_closed_with_history_and_trace(tmp_path: Path) -> None:
    coordinator = _coordinator(tmp_path)
    user_id, bookings = _add(tmp_path, 424242)

    with SqliteStore(tmp_path / "booksaver.db") as store:
        result = coordinator._run_booking(store, object(), user_id, bookings[0])
        history = SqliteCheckHistoryRepository(store).get_recent(bookings[0].booking_id)
        trace = SqliteCheckTraceRepository(store).get(result.check_id)

    assert result.failure_reason is not None
    assert result.failure_reason.code is FailureCode.AUTH_REQUIRED
    assert "--telegram-user-id 424242" in result.failure_reason.detail
    assert "No public-price or owner-session fallback" in result.failure_reason.detail
    assert history == [result]
    assert trace is not None


def test_scheduled_queue_skips_user_revoked_after_plan_without_cap_result(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path, checks=3)
    user_id, bookings = _add(tmp_path, 101, count=2)
    ran: list[str] = []

    def revoke_after_first(
        self: Any, store: SqliteStore, browser: Any, owner: int, booking: Any
    ) -> CheckResult:
        ran.append(booking.booking_id)
        SqliteUserRepository(store).set_access_state(user_id, UserAccessState.REVOKED)
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(  # type: ignore[method-assign]
        revoke_after_first, coordinator
    )
    coordinator.run_scheduled()

    assert len(ran) == 1
    assert coordinator.checks_today == {user_id: 1}
    unrun = next(booking for booking in bookings if booking.booking_id not in ran)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        second_history = SqliteCheckHistoryRepository(store).get_recent(unrun.booking_id)
    assert second_history == []


def test_one_users_missing_session_does_not_stop_another_users_scheduled_check(
    tmp_path: Path, monkeypatch: Any
) -> None:
    sessions = _session_repo(tmp_path)
    first_user_id, first_bookings = _add(tmp_path, 101)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        second_user = SqliteUserRepository(store).get_or_create_by_telegram_id(202, UserRole.USER)
        second_booking = make_booking("99999999-1111-4111-8111-111111111111")
        SqliteBookingRepository(store).add(second_booking, user_id=second_user.user_id)
    _seed_session(sessions, second_user.user_id)
    ran: list[int] = []

    class SecondUserMonitor:
        last_llm_calls_used = 0

        def __init__(self, **kwargs: Any) -> None:
            self.history = kwargs["check_history"]

        def set_llm_enabled(self, enabled: bool) -> None:
            return None

        def run_authenticated(self, booking: Any, snapshot: Any) -> CheckResult:
            ran.append(snapshot.metadata.owner_user_id)
            result = _failure(booking.booking_id)
            self.history.add(result)
            return result

    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.BookingComSearchMonitor",
        SecondUserMonitor,
    )
    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
        session_repository=sessions,
        inventory_synchronizer=_complete_sync,
    )

    coordinator.run_scheduled()

    assert ran == [second_user.user_id]
    with SqliteStore(tmp_path / "booksaver.db") as store:
        first_result = SqliteCheckHistoryRepository(store).get_recent(first_bookings[0].booking_id)[
            0
        ]
        second_result = SqliteCheckHistoryRepository(store).get_recent(second_booking.booking_id)[0]
    assert first_result.failure_reason is not None
    assert first_result.failure_reason.code is FailureCode.AUTH_REQUIRED
    assert second_result.failure_reason is not None
    assert second_result.failure_reason.code is FailureCode.STEP_FAILED
    assert first_user_id != second_user.user_id


def test_revoked_plan_snapshot_never_starts_browser(tmp_path: Path, monkeypatch: Any) -> None:
    user_id, _bookings = _add(tmp_path, 101)
    planned = threading.Event()
    browser_entries = 0

    def revoke_after_plan(**kwargs: Any) -> Any:
        plan = build_check_plan(**kwargs)
        with SqliteStore(tmp_path / "booksaver.db") as store:
            SqliteUserRepository(store).set_access_state(user_id, UserAccessState.REVOKED)
        planned.set()
        return plan

    class ObservedBrowser(AbstractContextManager[object]):
        def __enter__(self) -> object:
            nonlocal browser_entries
            browser_entries += 1
            return object()

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("booksaver.daemon.check_coordinator.build_check_plan", revoke_after_plan)
    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=ObservedBrowser,
        inventory_synchronizer=_complete_sync,
    )

    coordinator.run_scheduled()

    assert planned.is_set()
    assert browser_entries == 1
    assert coordinator.checks_today == {}


def test_midflight_revocation_keeps_history_but_suppresses_post_check_effects(
    tmp_path: Path, monkeypatch: Any
) -> None:
    user_id, bookings = _add(tmp_path, 101)
    history_written = threading.Event()
    revoked = threading.Event()
    pipeline_calls: list[list[CheckResult]] = []
    invalid_key_calls: list[list[CheckResult]] = []

    sessions = _session_repo(tmp_path)
    _seed_session(sessions, user_id)

    class RevocationMonitor:
        def __init__(self, **kwargs: Any) -> None:
            self.history = kwargs["check_history"]
            self.last_llm_calls_used = 0

        def set_llm_enabled(self, enabled: bool) -> None:
            return None

        def run_authenticated(self, booking: Any, _snapshot: Any) -> CheckResult:
            result = _failure(booking.booking_id)
            self.history.add(result)
            history_written.set()
            assert revoked.wait(2)
            return result

    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.BookingComSearchMonitor",
        RevocationMonitor,
    )
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.SavingsPipeline.process",
        lambda _self, results: pipeline_calls.append(results),
    )
    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, results: invalid_key_calls.append(results),
        browser_factory=BrowserContext,
        inventory_synchronizer=_complete_sync,
        session_repository=sessions,
    )

    def revoke_after_history() -> None:
        assert history_written.wait(2)
        with SqliteStore(tmp_path / "booksaver.db") as store:
            SqliteUserRepository(store).set_access_state(user_id, UserAccessState.REVOKED)
        revoked.set()

    revoker = threading.Thread(target=revoke_after_history)
    revoker.start()
    with SqliteStore(tmp_path / "booksaver.db") as store:
        result = coordinator._run_booking(store, object(), user_id, bookings[0])
    revoker.join(timeout=2)

    assert result.failure_reason is not None
    assert not revoker.is_alive()
    assert pipeline_calls == []
    assert invalid_key_calls == []
    with SqliteStore(tmp_path / "booksaver.db") as store:
        history = SqliteCheckHistoryRepository(store).get_recent(bookings[0].booking_id)
    assert len(history) == 1


def test_capped_notice_is_suppressed_for_revoked_user(tmp_path: Path, monkeypatch: Any) -> None:
    coordinator = _coordinator(tmp_path)
    user_id, _bookings = _add(tmp_path, 101)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        users.set_access_state(user_id, UserAccessState.REVOKED)
        monkeypatch.setenv("BOOKSAVER_TELEGRAM_BOT_TOKEN", "unused-token")

        class UnexpectedNotifier:
            def __init__(self, **kwargs: Any) -> None:
                raise AssertionError("revoked user notifier must not be created")

        monkeypatch.setattr(
            "booksaver.daemon.check_coordinator.TelegramNotifier",
            UnexpectedNotifier,
        )
        coordinator._send_capped_notice(store, user_id)


def test_llm_allowance_caps_monitor_then_disables_llm(tmp_path: Path, monkeypatch: Any) -> None:
    llm_counter = DailyCounter()
    coordinator = _coordinator(tmp_path, llm_calls=5, llm_counter=llm_counter)
    user_id, bookings = _add(tmp_path, 101)
    sessions = _session_repo(tmp_path)
    _seed_session(sessions, user_id)
    coordinator._session_repository = sessions
    llm_counter.increment(user_id, by=3)
    observed: list[tuple[int, bool]] = []

    class FakeMonitor:
        def __init__(self, **kwargs: Any) -> None:
            self.settings = kwargs["agent_settings"]
            self.history = kwargs["check_history"]
            self.enabled = True
            self.last_llm_calls_used = 0

        def set_llm_enabled(self, enabled: bool) -> None:
            self.enabled = enabled

        def run_authenticated(self, booking: Any, _snapshot: Any) -> CheckResult:
            observed.append((self.settings.max_llm_calls, self.enabled))
            self.last_llm_calls_used = self.settings.max_llm_calls if self.enabled else 0
            result = _failure(booking.booking_id)
            self.history.add(result)
            return result

    monkeypatch.setattr("booksaver.daemon.check_coordinator.BookingComSearchMonitor", FakeMonitor)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        coordinator._run_booking(store, object(), user_id, bookings[0])
        coordinator._run_booking(store, object(), user_id, bookings[0])

    assert observed == [(2, True), (4, False)]
    assert coordinator.llm_calls_today[user_id] == 5


def test_runtime_signed_out_failure_marks_only_resolved_revision_for_reauth(
    tmp_path: Path, monkeypatch: Any
) -> None:
    sessions = _session_repo(tmp_path)
    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
        session_repository=sessions,
        inventory_synchronizer=_complete_sync,
    )
    user_id, bookings = _add(tmp_path, 101)
    _seed_session(sessions, user_id)

    class SignedOutMonitor:
        last_llm_calls_used = 0

        def __init__(self, **kwargs: Any) -> None:
            self.history = kwargs["check_history"]

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
        "booksaver.daemon.check_coordinator.BookingComSearchMonitor",
        SignedOutMonitor,
    )

    with SqliteStore(tmp_path / "booksaver.db") as store:
        coordinator._run_booking(store, object(), user_id, bookings[0])

    status = sessions.status(user_id)
    assert status.health.value == "reauth_required"


def test_scheduled_and_manual_boundary_uses_normal_history_trace_and_savings_pipeline(
    tmp_path: Path,
) -> None:
    browser = FakeInteractiveBrowser(
        titles=["Hotel Test"],
        page_text=("Standard Double\n€ 350.00\nFree cancellation before 30 August 2026"),
    )
    browser.property_url = (
        "https://www.booking.com/hotel/test.html?checkin=2026-09-01&"
        "checkout=2026-09-05&group_adults=2"
    )
    cfg = _config(tmp_path)
    sessions = _session_repo(tmp_path)
    coordinator = CheckCoordinator(
        cfg,
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: NullLLMFactory(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=lambda: ExistingBrowserContext(browser),
        session_repository=sessions,
        inventory_synchronizer=_complete_sync,
    )
    user_id, bookings = _add(tmp_path, 101)
    _seed_session(sessions, user_id)

    coordinator.run_scheduled()

    with SqliteStore(tmp_path / "booksaver.db") as store:
        history = SqliteCheckHistoryRepository(store).get_recent(bookings[0].booking_id)
        savings = SqliteSavingsRepository(store).list_all()
        trace = SqliteCheckTraceRepository(store).get(history[0].check_id)
    assert history[0].live_price is not None
    assert str(history[0].live_price.amount) == "350.00"
    assert len(savings) == 1
    assert trace is not None


def test_stopping_refuses_new_immediate_work(tmp_path: Path) -> None:
    stop = threading.Event()
    stop.set()
    coordinator = CheckCoordinator(
        _config(tmp_path),
        stop,
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
        inventory_synchronizer=_complete_sync,
    )

    assert (
        coordinator.request_immediate(101, "booking", lambda _outcome: None)
        is ImmediateAdmission.STOPPING
    )


def test_bookings_request_discovers_and_projects_authenticated_inventory(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(101, UserRole.USER)
    _seed_session(sessions, user.user_id)

    class InventoryBrowser:
        def restore_cookies(self, _cookies: bytes) -> None:
            return None

        def open_page(self, url: str) -> PageContent:
            return PageContent(
                url,
                """
                    <main data-testid="bookings-list"
                          data-inventory-scopes="upcoming,past,cancelled">
                  <article data-testid="reservation-card"
                    data-reservation-id="remote-1"
                    data-confirmation-id="CONF-1"
                    data-status="confirmed"
                    data-property-name="Synchronized Hotel"
                    data-property-url="hotel-ref"
                    data-checkin="2026-09-01"
                    data-checkout="2026-09-05"
                    data-room-type="Double"
                    data-total-amount="400"
                    data-currency="EUR"
                    data-refundable="true"
                    data-adults="2"></article>
                </main>
                """,
                "",
            )

        def is_authenticated(self) -> bool:
            return True

        def get_cookies(self) -> bytes:
            return b"[]"

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=lambda: ExistingBrowserContext(InventoryBrowser()),
        session_repository=sessions,
    )
    completed = threading.Event()
    outcomes: list[InventoryCompletion] = []

    assert (
        coordinator.request_inventory(
            101,
            lambda outcome: (outcomes.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert outcomes[0].report is not None and outcomes[0].report.succeeded
    assert outcomes[0].reservations[0].observation.property_name == ("Synchronized Hotel")
    with SqliteStore(tmp_path / "booksaver.db") as store:
        projected = SqliteBookingRepository(store).list_active_for_user(user.user_id)
    assert len(projected) == 1
    assert coordinator.llm_calls_today == {}


def test_incident_resolution_runs_only_after_inventory_browser_closes(
    tmp_path: Path,
) -> None:
    _add(tmp_path, 101)
    browser_closed = threading.Event()
    recorded: list[Any] = []

    class ClosingBrowserContext(AbstractContextManager[object]):
        def __enter__(self) -> object:
            return object()

        def __exit__(self, *args: object) -> None:
            browser_closed.set()

    class Recorder:
        def resolve_deterministic_success(self, **kwargs: Any) -> int:
            assert browser_closed.is_set()
            recorded.append(kwargs["step_id"])
            return 0

        def record_safely(self, _draft: Any) -> None:
            raise AssertionError("deterministic success must not create a draft")

    class RecorderContext(AbstractContextManager[Recorder]):
        def __enter__(self) -> Recorder:
            assert browser_closed.is_set()
            return Recorder()

        def __exit__(self, *args: object) -> None:
            return None

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=ClosingBrowserContext,
        inventory_synchronizer=_complete_sync,
        incident_recorder_factory=RecorderContext,
    )
    completed = threading.Event()
    outcomes: list[InventoryCompletion] = []

    assert (
        coordinator.request_inventory(
            101,
            lambda outcome: (outcomes.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert outcomes[0].report is not None and outcomes[0].report.succeeded
    assert recorded
    assert coordinator.llm_calls_today == {}


def test_incident_factory_failure_never_changes_inventory_completion(
    tmp_path: Path,
) -> None:
    _add(tmp_path, 101)
    browser_closed = threading.Event()

    class ClosingBrowserContext(AbstractContextManager[object]):
        def __enter__(self) -> object:
            return object()

        def __exit__(self, *args: object) -> None:
            browser_closed.set()

    def failing_incident_factory() -> AbstractContextManager[Any]:
        assert browser_closed.is_set()
        raise RuntimeError("incident store unavailable")

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=ClosingBrowserContext,
        inventory_synchronizer=_complete_sync,
        incident_recorder_factory=failing_incident_factory,
    )
    completed = threading.Event()
    outcomes: list[InventoryCompletion] = []

    assert (
        coordinator.request_inventory(
            101,
            lambda outcome: (outcomes.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert outcomes[0].report is not None and outcomes[0].report.succeeded
    assert browser_closed.is_set()


def test_predictable_inventory_failure_does_not_open_incident_sink(
    tmp_path: Path,
) -> None:
    _add(tmp_path, 101)

    def predictable_failure(
        _store: Any,
        _browser: Any,
        _user_id: int,
        _trigger: Any,
    ) -> SynchronizationReport:
        return SynchronizationReport(
            run_id="known-auth",
            completeness=InventoryCompleteness.FAILED,
            discovered=0,
            eligible=0,
            ineligible=0,
            failure_code=SynchronizationFailureCode.AUTH_REQUIRED,
            failure_detail="send /connect",
        )

    def forbidden_factory() -> AbstractContextManager[Any]:
        raise AssertionError("predictable failure must not reach the incident sink")

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
        inventory_synchronizer=predictable_failure,
        incident_recorder_factory=forbidden_factory,
    )
    completed = threading.Event()
    outcomes: list[InventoryCompletion] = []

    assert (
        coordinator.request_inventory(
            101,
            lambda outcome: (outcomes.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert outcomes[0].report is not None
    assert outcomes[0].report.failure_code is SynchronizationFailureCode.AUTH_REQUIRED


def test_model_assisted_success_builds_one_sanitized_step_draft() -> None:
    diagnosis = TerminalBrowserDiagnosis(
        reason=TerminalBrowserReason.POSTCONDITION_SATISFIED,
        step_id=DomStepId.PRICE_PROPERTY_OPEN,
        provenance=DiagnosisProvenance.SONNET_RECOVERED,
        confidence=1.0,
        evidence=frozenset(),
        operator_action=OperatorAction.NONE,
    )
    attempt = ModelAttemptAudit(
        reservation_id="reservation-test",
        job_id="job-test",
        ordinal=1,
        provider="anthropic",
        model="claude-sonnet-5",
        role=ModelRole.RECOVERY.value,
        trigger="initial_ambiguous",
        outcome="recovered",
        status=ReservationStatus.CHARGED,
        reserved_cost=UsdAmount(1),
        charged_cost=UsdAmount(1),
        usage=None,
        latency_ms=1,
    )

    class Budget:
        def ordered_attempts(self) -> tuple[ModelAttemptAudit, ...]:
            return (attempt,)

    result = CheckResult.success(
        booking_id="booking-test",
        checked_at=datetime.now(UTC),
        live_price=Money.of("100", "USD"),
        extraction_method=ExtractionMethod.AGENT,
        assisted_diagnoses=(diagnosis,),
    )
    observed_at = datetime.now(UTC)

    class EvidenceBrowser:
        def observe(self) -> Observation:
            return Observation(
                url="https://private.example/reservation?token=secret",
                title="Secret property",
                text="confirmation 123456789",
                elements=(
                    ElementInfo(
                        ref="e1",
                        role="button",
                        label="Secret reservation",
                        href="https://private.example/reservation/123",
                    ),
                    ElementInfo(ref="e2", role="input", label="Private confirmation"),
                    ElementInfo(ref="e3", role="reservation-card", label="Private card"),
                ),
                screenshot=b"raw image must never cross the boundary",
            )

    evidence = CheckCoordinator._capture_incident_evidence(  # noqa: SLF001
        browser=EvidenceBrowser(),
        adaptive_job=AdaptiveBrowserJobContext(7, object(), Budget()),  # type: ignore[arg-type]
        check_result=result,
        check_trace=CheckTrace(
            check_id=result.check_id,
            booking_id=result.booking_id,
            created_at=observed_at,
            events=(
                TraceEvent(
                    seq=0,
                    at=observed_at,
                    kind=TraceKind.AGENT_OUTCOME,
                    detail=json.dumps(
                        {
                            "outcome": "executed",
                            "verified": True,
                            "detail": "private rendered content",
                        }
                    ),
                ),
            ),
        ),
    )
    drafts, resolved = CheckCoordinator._incident_handoffs(  # noqa: SLF001
        user_id=7,
        adaptive_job=AdaptiveBrowserJobContext(7, object(), Budget()),  # type: ignore[arg-type]
        inventory_report=None,
        check_result=result,
        evidence=evidence,
    )

    assert evidence.structural_roles == ("button", "textbox")
    assert evidence.action_outcomes == ("executed", "verified")
    assert "private" not in repr(evidence).casefold()
    assert "secret" not in repr(evidence).casefold()
    assert len(drafts) == 1
    assert drafts[0].occurrence.step_id is DomStepId.PRICE_PROPERTY_OPEN
    assert drafts[0].diagnostic_bundle is not None
    assert drafts[0].diagnostic_bundle.structural_roles == ("button", "textbox")
    assert drafts[0].diagnostic_bundle.action_outcomes == ("executed", "verified")
    assert drafts[0].diagnostic_bundle.structural_image is None
    assert all(step is not DomStepId.PRICE_PROPERTY_OPEN for _journey, step, _at in resolved)


def test_inventory_interpreter_call_is_charged_to_requesting_user(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(101, UserRole.USER)
    _seed_session(sessions, user.user_id)

    class InventoryBrowser:
        def restore_cookies(self, _cookies: bytes) -> None:
            return None

        def open_page(self, url: str) -> PageContent:
            return PageContent(
                url,
                '<main data-inventory-complete="true">New layout</main>',
                "Recovered reservation remote-assisted evidence",
            )

        def is_authenticated(self) -> bool:
            return True

        def get_cookies(self) -> bytes:
            return b"[]"

    class Interpreter:
        def interpret(self, _page_text: str, source_url: str) -> tuple[ReservationObservation, ...]:
            return (
                ReservationObservation(
                    remote_id="remote-assisted",
                    lifecycle=ReservationLifecycle.UPCOMING,
                    observed_at=datetime.now(UTC),
                    confirmation_id="CONF-ASSISTED",
                    property_name="Assisted Hotel",
                    property_ref="assisted-hotel",
                    check_in=date(2027, 1, 10),
                    check_out=date(2027, 1, 12),
                    room_type="King room",
                    booked_total=Money.of("200", "USD"),
                    refundable=True,
                    occupancy=Occupancy(2, 0, 1),
                    source_url=source_url,
                    extraction_method="llm_inventory",
                ),
            )

    class Factory(NullLLMFactory):
        def inventory_interpreter_for_user(
            self, _user_id: int, role: str = "inventory_interpreter"
        ) -> Interpreter:
            assert role == "inventory_interpreter"
            return Interpreter()

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: Factory(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=lambda: ExistingBrowserContext(InventoryBrowser()),
        session_repository=sessions,
    )
    completed = threading.Event()
    outcomes: list[InventoryCompletion] = []

    assert (
        coordinator.request_inventory(
            101,
            lambda outcome: (outcomes.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert outcomes[0].report is not None
    # The model call is charged and its grounded positive identity is retained,
    # but LLM-only facts cannot prove the upcoming-scope traversal complete.
    assert outcomes[0].report.recovery_outcome is InventoryRecoveryOutcome.UNAVAILABLE
    assert outcomes[0].report.completeness is InventoryCompleteness.INCOMPLETE
    assert outcomes[0].report.llm_calls_used == 1
    assert outcomes[0].report.recovery_audit is not None
    assert outcomes[0].report.recovery_audit.roles == ("inventory_interpreter",)
    assert coordinator.llm_calls_today == {user.user_id: 1}


def test_inventory_with_no_daily_allowance_stays_deterministic_only(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(101, UserRole.USER)
    _seed_session(sessions, user.user_id)
    cfg = _config(tmp_path)
    calls = DailyCounter()
    daily_limit = cfg.limits_settings.max_llm_calls_per_user_per_day
    calls.increment(user.user_id, by=daily_limit)

    class Browser:
        def restore_cookies(self, _cookies: bytes) -> None:
            return None

        def open_page(self, url: str) -> PageContent:
            return PageContent(url, "<main>Changed layout</main>", "Unknown layout")

        def is_authenticated(self) -> bool:
            return True

        def get_cookies(self) -> bytes:
            return b"[]"

    completed = threading.Event()
    outcomes: list[InventoryCompletion] = []
    coordinator = CheckCoordinator(
        cfg,
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: (_ for _ in ()).throw(
            AssertionError("factory must not resolve without allowance")
        ),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=lambda: ExistingBrowserContext(Browser()),
        session_repository=sessions,
        llm_calls_today=calls,
    )

    assert (
        coordinator.request_inventory(
            101,
            lambda outcome: (outcomes.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert outcomes[0].report is not None
    assert outcomes[0].report.recovery_outcome is InventoryRecoveryOutcome.UNAVAILABLE
    assert outcomes[0].report.llm_calls_used == 0
    assert coordinator.llm_calls_today[user.user_id] == daily_limit


def test_inventory_personal_key_failure_is_preserved_with_setkey_guidance(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(101, UserRole.USER)
    _seed_session(sessions, user.user_id)

    class Browser:
        def restore_cookies(self, _cookies: bytes) -> None:
            return None

        def open_page(self, url: str) -> PageContent:
            return PageContent(url, "<main>Changed layout</main>", "Changed layout")

        def is_authenticated(self) -> bool:
            return True

        def get_cookies(self) -> bytes:
            return b"[]"

    class Factory(NullLLMFactory):
        def inventory_interpreter_for_user(
            self, requested_user_id: int, role: str = "inventory_interpreter"
        ) -> None:
            assert requested_user_id == user.user_id
            assert role == "inventory_interpreter"
            raise UserKeyInvalidError(requested_user_id, "private detail")

    completed = threading.Event()
    outcomes: list[InventoryCompletion] = []
    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: Factory(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=lambda: ExistingBrowserContext(Browser()),
        session_repository=sessions,
    )

    assert (
        coordinator.request_inventory(
            101,
            lambda outcome: (outcomes.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    report = outcomes[0].report
    assert report is not None
    assert report.failure_code is SynchronizationFailureCode.USER_KEY_INVALID
    assert "/setkey" in (report.failure_detail or "")
    assert "private detail" not in (report.failure_detail or "")
    assert report.llm_calls_used == 0
    assert report.recovery_audit is not None
    assert report.recovery_audit.outcome is InventoryRecoveryOutcome.UNAVAILABLE


def test_check_now_synchronizes_before_resolving_booking(tmp_path: Path) -> None:
    events: list[str] = []

    def synchronize(
        _store: SqliteStore, _browser: Any, _user_id: int, trigger: Any
    ) -> SynchronizationReport:
        events.append(trigger.value)
        return _complete_sync(_store, _browser, _user_id, trigger)

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
        inventory_synchronizer=synchronize,
    )
    _user_id, bookings = _add(tmp_path, 101)
    completed = threading.Event()

    def fake_run(self: Any, store: Any, browser: Any, owner: int, booking: Any) -> CheckResult:
        events.append("price_check")
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(fake_run, coordinator)  # type: ignore[method-assign]
    coordinator.request_immediate(101, bookings[0].booking_id, lambda _outcome: completed.set())
    assert completed.wait(1)

    assert events == [SynchronizationTrigger.CHECK_NOW.value, "price_check"]


def test_agentic_inventory_routes_owner_and_disclosed_invitee_without_legacy_browser(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    disclosure_version = _config(tmp_path).agentic_browser_settings.disclosure_version
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        users.link_telegram_id(owner.user_id, 101)
        invitee = users.get_or_create_by_telegram_id(202, UserRole.USER)
        SqliteAgenticDisclosureConsentRepository(store).acknowledge(
            user_id=invitee.user_id,
            disclosure_version=disclosure_version,
            acknowledged_at=datetime.now(UTC),
        )
    _seed_session(sessions, owner.user_id)
    _seed_session(sessions, invitee.user_id)
    executor = FakeInventoryBrowserExecutor(
        [_agentic_inventory_result(), _agentic_inventory_result()]
    )
    legacy_browser_opens: list[None] = []

    def legacy_browser_factory() -> BrowserContext:
        legacy_browser_opens.append(None)
        return BrowserContext()

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=legacy_browser_factory,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _budget, _leases: executor,
    )
    completions: list[InventoryCompletion] = []

    for telegram_user_id in (101, 202):
        completed = threading.Event()
        assert (
            coordinator.request_inventory(
                telegram_user_id,
                lambda outcome, event=completed: (completions.append(outcome), event.set()),
            )
            is ImmediateAdmission.ACCEPTED
        )
        assert completed.wait(1)

    assert [request.owner_user_id for request in executor.requests] == [
        owner.user_id,
        invitee.user_id,
    ]
    assert legacy_browser_opens == []
    assert all(
        completion.report is not None
        and completion.report.completeness is InventoryCompleteness.INCOMPLETE
        for completion in completions
    )


def test_undisclosed_invitee_stays_on_legacy_inventory_route(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        invitee = SqliteUserRepository(store).get_or_create_by_telegram_id(202, UserRole.USER)
    executor = FakeInventoryBrowserExecutor([_agentic_inventory_result()])
    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
        agentic_inventory_executor_factory=lambda _budget, _leases: executor,
    )
    legacy_calls: list[tuple[int, SynchronizationTrigger]] = []

    def legacy_sync(
        self: CheckCoordinator,
        store: SqliteStore,
        _browser: Any,
        user_id: int,
        trigger: SynchronizationTrigger,
    ) -> SynchronizationReport:
        legacy_calls.append((user_id, trigger))
        return _complete_sync(store, _browser, user_id, trigger)

    coordinator._synchronize_user = MethodType(legacy_sync, coordinator)  # type: ignore[method-assign]
    completed = threading.Event()

    assert (
        coordinator.request_inventory(202, lambda _outcome: completed.set())
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert legacy_calls == [(invitee.user_id, SynchronizationTrigger.BOOKINGS)]
    assert executor.requests == []


def test_agentic_inventory_terminal_failure_never_falls_back_to_legacy_in_same_job(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        invitee = SqliteUserRepository(store).get_or_create_by_telegram_id(202, UserRole.USER)
        SqliteAgenticDisclosureConsentRepository(store).acknowledge(
            user_id=invitee.user_id,
            disclosure_version=_config(tmp_path).agentic_browser_settings.disclosure_version,
            acknowledged_at=datetime.now(UTC),
        )
    _seed_session(sessions, invitee.user_id)
    executor = FakeInventoryBrowserExecutor(
        [InventoryExecutionResult(InventoryExecutionStatus.PROVIDER_FAILURE)]
    )
    legacy_calls: list[None] = []

    def legacy_browser_factory() -> BrowserContext:
        legacy_calls.append(None)
        return BrowserContext()

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=legacy_browser_factory,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _budget, _leases: executor,
    )
    completed = threading.Event()
    completions: list[InventoryCompletion] = []

    assert (
        coordinator.request_inventory(
            202,
            lambda outcome: (completions.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert len(executor.requests) == 1
    assert legacy_calls == []
    assert completions[0].report is not None
    assert completions[0].report.completeness is InventoryCompleteness.FAILED
    assert completions[0].report.failure_code is SynchronizationFailureCode.NAVIGATION_FAILED


def test_configured_agentic_inventory_without_executor_fails_closed(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        SqliteUserRepository(store).link_telegram_id(owner.user_id, 101)
    _seed_session(sessions, owner.user_id)
    legacy_browser_opens: list[None] = []

    def legacy_browser_factory() -> BrowserContext:
        legacy_browser_opens.append(None)
        return BrowserContext()

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=legacy_browser_factory,
        session_repository=sessions,
    )
    completed = threading.Event()
    completions: list[InventoryCompletion] = []

    assert (
        coordinator.request_inventory(
            101,
            lambda outcome: (completions.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert legacy_browser_opens == []
    assert completions[0].report is not None
    assert completions[0].report.completeness is InventoryCompleteness.FAILED
    assert completions[0].report.failure_code is SynchronizationFailureCode.NAVIGATION_FAILED


def test_current_agentic_positive_allows_selected_check_with_shared_residual_limits(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        invitee = SqliteUserRepository(store).get_or_create_by_telegram_id(202, UserRole.USER)
        SqliteAgenticDisclosureConsentRepository(store).acknowledge(
            user_id=invitee.user_id,
            disclosure_version=_config(tmp_path).agentic_browser_settings.disclosure_version,
            acknowledged_at=datetime.now(UTC),
        )
    _seed_session(sessions, invitee.user_id)
    source_booking = make_booking("agentic-current-positive")
    booking_id = _seed_inventory_projection(
        tmp_path,
        user_id=invitee.user_id,
        remote_id="remote-current-positive",
        booking=source_booking,
    )
    usage = ExecutionUsage(
        total_actions=4,
        computer_use_actions=2,
        cost=UsdAmount(250_000),
    )
    executor = FakeInventoryBrowserExecutor(
        [
            _agentic_inventory_result(
                (_observed_inventory_reservation(source_booking, "remote-current-positive"),),
                usage=usage,
            )
        ]
    )
    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _budget, _leases: executor,
    )
    residual_limits: list[Any] = []
    ran: list[str] = []
    ran: list[str] = []

    def run_selected(
        self: CheckCoordinator,
        _store: Any,
        _browser: Any,
        _owner: int,
        booking: Any,
    ) -> CheckResult:
        context = self._current_agentic_job()  # noqa: SLF001
        assert context is not None
        residual_limits.append(context.remaining_limits())
        ran.append(booking.booking_id)
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(run_selected, coordinator)  # type: ignore[method-assign]
    completed = threading.Event()
    completions: list[ImmediateCompletion] = []

    assert (
        coordinator.request_immediate(
            202,
            booking_id,
            lambda outcome: (completions.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert completions[0].kind is ImmediateCompletionKind.RESULT
    assert completions[0].result is not None
    assert executor.requests[0].limits.max_actions == 15
    assert executor.requests[0].limits.max_computer_use_actions == 6
    assert executor.requests[0].limits.max_job_cost == UsdAmount(1_000_000)
    assert residual_limits[0] is not None
    assert residual_limits[0].deadline == executor.requests[0].limits.deadline
    assert residual_limits[0].max_actions == 11
    assert residual_limits[0].max_computer_use_actions == 4
    assert residual_limits[0].max_job_cost == UsdAmount(750_000)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        latest = SqliteAccountReservationRepository(store).latest_run_for_user(invitee.user_id)
    assert latest is not None
    assert latest.completeness is InventoryCompleteness.INCOMPLETE


def test_selected_booking_without_current_agentic_positive_is_rejected(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        invitee = SqliteUserRepository(store).get_or_create_by_telegram_id(202, UserRole.USER)
        SqliteAgenticDisclosureConsentRepository(store).acknowledge(
            user_id=invitee.user_id,
            disclosure_version=_config(tmp_path).agentic_browser_settings.disclosure_version,
            acknowledged_at=datetime.now(UTC),
        )
    _seed_session(sessions, invitee.user_id)
    stale_source = make_booking("agentic-stale")
    current_source = make_booking("agentic-current")
    stale_booking_id = _seed_inventory_projection(
        tmp_path,
        user_id=invitee.user_id,
        remote_id="remote-stale",
        booking=stale_source,
    )
    current_booking_id = _seed_inventory_projection(
        tmp_path,
        user_id=invitee.user_id,
        remote_id="remote-current",
        booking=current_source,
    )
    executor = FakeInventoryBrowserExecutor(
        [
            _agentic_inventory_result(
                (_observed_inventory_reservation(current_source, "remote-current"),)
            )
        ]
    )
    price_browser_opens: list[None] = []

    def browser_factory() -> BrowserContext:
        price_browser_opens.append(None)
        return BrowserContext()

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=browser_factory,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _budget, _leases: executor,
    )
    completed = threading.Event()
    completions: list[ImmediateCompletion] = []

    assert (
        coordinator.request_immediate(
            202,
            stale_booking_id,
            lambda outcome: (completions.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert completions[0].kind is ImmediateCompletionKind.UNAVAILABLE
    assert "not positively verified" in (completions[0].unavailable_detail or "")
    assert price_browser_opens == []
    with SqliteStore(tmp_path / "booksaver.db") as store:
        bookings = SqliteBookingRepository(store)
        assert {item.booking_id for item in bookings.list_active_for_user(invitee.user_id)} == {
            stale_booking_id,
            current_booking_id,
        }


def test_selected_check_surfaces_agentic_inventory_terminal_detail(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        invitee = SqliteUserRepository(store).get_or_create_by_telegram_id(202, UserRole.USER)
        SqliteAgenticDisclosureConsentRepository(store).acknowledge(
            user_id=invitee.user_id,
            disclosure_version=_config(tmp_path).agentic_browser_settings.disclosure_version,
            acknowledged_at=datetime.now(UTC),
        )
    _seed_session(sessions, invitee.user_id)
    source = make_booking("agentic-terminal-detail")
    booking_id = _seed_inventory_projection(
        tmp_path,
        user_id=invitee.user_id,
        remote_id="agentic-terminal-detail-remote",
        booking=source,
    )
    executor = FakeInventoryBrowserExecutor(
        [InventoryExecutionResult(InventoryExecutionStatus.BOT_WALL)]
    )
    price_browser_opens: list[None] = []

    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=lambda: (
            price_browser_opens.append(None) or BrowserContext()
        ),
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _budget, _leases: executor,
    )
    completed = threading.Event()
    completions: list[ImmediateCompletion] = []

    assert (
        coordinator.request_immediate(
            202,
            booking_id,
            lambda outcome: (completions.append(outcome), completed.set()),
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert completions[0].kind is ImmediateCompletionKind.UNAVAILABLE
    assert "bot-verification wall" in (completions[0].unavailable_detail or "")
    assert price_browser_opens == []


def test_agentic_price_exhausted_shared_allowance_reports_budget(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    booking = make_booking("agentic-exhausted-shared-budget")
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        users.link_telegram_id(owner.user_id, 101)
        SqliteBookingRepository(store).add(booking, user_id=owner.user_id)
    _seed_session(sessions, owner.user_id)
    config = _config(tmp_path)
    config.agentic_browser_settings = replace(
        config.agentic_browser_settings,
        routing=ExecutionRoutingMode.OWNER_CANARY,
    )
    executor_calls: list[None] = []
    coordinator = CheckCoordinator(
        config,
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
        session_repository=sessions,
        agentic_executor_factory=lambda _budget, _leases: (
            executor_calls.append(None) or object()
        ),
    )
    exhausted = AgenticBrowserJobContext(
        local_user_id=owner.user_id,
        job_kind=BrowserJobKind.CHECK_NOW,
        job_id="agentic-exhausted-shared-budget",
        deadline=datetime.now(UTC) + timedelta(minutes=3),
        job_limit_micro_usd=config.agent_settings.max_job_cost_micro_usd,
        daily_limit_micro_usd=config.agent_settings.max_deployment_daily_cost_micro_usd,
        total_actions=15,
    )

    with SqliteStore(tmp_path / "booksaver.db") as store:
        with coordinator._resume_agentic_job(exhausted):  # noqa: SLF001
            result = coordinator._run_booking(  # noqa: SLF001
                store,
                object(),
                owner.user_id,
                booking,
            )
        history = SqliteCheckHistoryRepository(store).get_recent(booking.booking_id)
        trace = SqliteCheckTraceRepository(store).get(result.check_id)

    assert result.failure_reason is not None
    assert result.failure_reason.code is FailureCode.BUDGET_EXCEEDED
    assert executor_calls == []
    assert history == [result]
    assert trace is not None


def test_coordinated_job_never_starts_unbudgeted_legacy_llm_fallback(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    sessions = _session_repo(tmp_path)
    booking = make_booking("coordinated-no-unbudgeted-fallback")
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        users.link_telegram_id(owner.user_id, 101)
        SqliteBookingRepository(store).add(booking, user_id=owner.user_id)
    _seed_session(sessions, owner.user_id)
    builder_calls: list[None] = []
    observed_factories: list[object | None] = []

    def build_factory(_cfg: Config, _store: SqliteStore) -> object:
        builder_calls.append(None)
        return object()

    class Monitor:
        last_agentic_outcome = None
        last_agent_steps_used = 0
        last_llm_calls_used = 0

        def __init__(self, **kwargs: Any) -> None:
            self.history = kwargs["check_history"]
            observed_factories.append(kwargs["llm_factory"])

        def set_llm_enabled(self, _enabled: bool) -> None:
            return None

        def run_authenticated(self, selected: Any, _snapshot: Any) -> CheckResult:
            result = _failure(selected.booking_id)
            self.history.add(result)
            return result

    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.BookingComSearchMonitor",
        Monitor,
    )
    coordinator = CheckCoordinator(
        _config(tmp_path),
        threading.Event(),
        llm_factory_builder=build_factory,
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
        session_repository=sessions,
    )

    with SqliteStore(tmp_path / "booksaver.db") as store:
        with coordinator._adaptive_job_scope(  # noqa: SLF001
            store,
            owner.user_id,
            BrowserJobKind.CHECK_NOW,
        ):
            coordinator._run_booking(  # noqa: SLF001
                store,
                object(),
                owner.user_id,
                booking,
            )

    assert builder_calls == [None]
    assert observed_factories == [None]


def test_scheduled_agentic_plan_contains_only_current_run_positive_bookings(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        invitee = SqliteUserRepository(store).get_or_create_by_telegram_id(202, UserRole.USER)
        SqliteAgenticDisclosureConsentRepository(store).acknowledge(
            user_id=invitee.user_id,
            disclosure_version=_config(tmp_path).agentic_browser_settings.disclosure_version,
            acknowledged_at=datetime.now(UTC),
        )
    _seed_session(sessions, invitee.user_id)
    stale_source = make_booking("scheduled-stale")
    current_source = make_booking("scheduled-current")
    stale_booking_id = _seed_inventory_projection(
        tmp_path,
        user_id=invitee.user_id,
        remote_id="scheduled-remote-stale",
        booking=stale_source,
    )
    current_booking_id = _seed_inventory_projection(
        tmp_path,
        user_id=invitee.user_id,
        remote_id="scheduled-remote-current",
        booking=current_source,
    )
    executor = FakeInventoryBrowserExecutor(
        [
            _agentic_inventory_result(
                (
                    _observed_inventory_reservation(
                        current_source,
                        "scheduled-remote-current",
                    ),
                )
            )
        ]
    )
    coordinator = CheckCoordinator(
        _config(tmp_path, checks=10),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _budget, _leases: executor,
    )
    ran: list[str] = []

    def run_planned(
        _self: CheckCoordinator,
        _store: Any,
        _browser: Any,
        _owner: int,
        booking: Any,
    ) -> CheckResult:
        ran.append(booking.booking_id)
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(run_planned, coordinator)  # type: ignore[method-assign]
    planned_at = datetime.now(UTC) - timedelta(seconds=1)
    identity = _scheduled_slot(tmp_path, invitee.user_id, planned_at)

    assert (
        coordinator.run_scheduled_slot(identity, ScheduleSettings(), datetime.now(UTC))
        is ScheduledAdmission.COMPLETED
    )

    assert ran == [current_booking_id]
    assert stale_booking_id not in ran


def test_compatibility_scheduler_reuses_inventory_residual_agentic_limits(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        SqliteUserRepository(store).link_telegram_id(owner.user_id, 101)
    _seed_session(sessions, owner.user_id)
    source_booking = make_booking("scheduled-shared-residual")
    current_booking_id = _seed_inventory_projection(
        tmp_path,
        user_id=owner.user_id,
        remote_id="scheduled-shared-residual-remote",
        booking=source_booking,
    )
    usage = ExecutionUsage(
        total_actions=4,
        computer_use_actions=2,
        cost=UsdAmount(250_000),
    )
    executor = FakeInventoryBrowserExecutor(
        [
            _agentic_inventory_result(
                (
                    _observed_inventory_reservation(
                        source_booking,
                        "scheduled-shared-residual-remote",
                    ),
                ),
                usage=usage,
            )
        ]
    )
    coordinator = CheckCoordinator(
        _config(tmp_path, checks=10, llm_calls=20),
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: object(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=BrowserContext,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _budget, _leases: executor,
    )
    residual_limits: list[Any] = []
    ran: list[str] = []

    def run_planned(
        self: CheckCoordinator,
        _store: Any,
        _browser: Any,
        _owner: int,
        booking: Any,
    ) -> CheckResult:
        context = self._current_agentic_job()  # noqa: SLF001
        assert context is not None
        residual_limits.append(context.remaining_limits())
        ran.append(booking.booking_id)
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(run_planned, coordinator)  # type: ignore[method-assign]

    coordinator.run_scheduled()

    assert ran == [current_booking_id]
    assert len(residual_limits) == 1
    assert residual_limits[0] is not None
    assert residual_limits[0].deadline == executor.requests[0].limits.deadline
    assert residual_limits[0].max_actions == 11
    assert residual_limits[0].max_computer_use_actions == 4
    assert residual_limits[0].max_job_cost == UsdAmount(750_000)
