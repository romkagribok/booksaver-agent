from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MethodType
from typing import Any
from unittest.mock import MagicMock

import pytest

from booksaver.daemon.check_coordinator import (
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
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationFailureCode,
    SynchronizationReport,
    SynchronizationTrigger,
)
from booksaver.domain.agent import (
    AgentSettings,
)
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionUsage,
    ObservationSource,
    PriceExecutorKind,
    QualificationStatus,
    RedactedProvenance,
    RefundabilityEvidence,
)
from booksaver.domain.check_result import (
    CheckResult,
    FailureCode,
    FailureReason,
)
from booksaver.domain.inventory_executor import (
    InventoryExecutionResult,
    InventoryExecutionStatus,
    InventoryScope,
    ObservedInventoryScope,
    ObservedReservation,
)
from booksaver.domain.model_policy import (
    BrowserJobKind,
    UsdAmount,
)
from booksaver.domain.models import Booking, Config
from booksaver.domain.schedule import (
    ScheduledAdmission,
    ScheduledCheckSlot,
    ScheduleSettings,
    SlotIdentity,
    SlotStatus,
)
from booksaver.domain.user import UserAccessState, UserRole
from booksaver.domain.user_session import (
    UserSessionHealth,
    UserSessionMetadata,
    UserSessionSnapshot,
)
from booksaver.domain.value_objects import (
    CheckInterval,
    DataDirectory,
    LimitsSettings,
    NotificationSettings,
    Platform,
    StayDates,
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
    SqliteAgenticQualificationRepository,
    SqliteBookingRepository,
    SqliteCheckHistoryRepository,
    SqliteCheckTraceRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.monitor.user_limits import DailyCounter, build_check_plan
from tests.support.bookings import seed_booking
from tests.support.executors import FakeInventoryBrowserExecutor
from tests.unit.monitor.fakes import make_booking


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


_TEST_SESSION_KEY = "wGeBQ1NevJlDl9nkMrKT4uh90w2yK8sBgKYrp4r1pTk="


def _future_booking(booking_id: str) -> Booking:
    # Inventory projection evaluates eligibility against the real observation time.
    check_in = datetime.now(UTC).date() + timedelta(days=30)
    return replace(
        make_booking(booking_id),
        stay_dates=StayDates(check_in=check_in, check_out=check_in + timedelta(days=4)),
    )


def _complete_sync(_store: SqliteStore, _user_id: int, _trigger: Any) -> SynchronizationReport:
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


def _config(tmp_path: Path, *, checks: int = 3) -> Config:
    return Config(
        check_interval=CheckInterval.parse("12h"),
        data_directory=DataDirectory(tmp_path),
        notification_settings=NotificationSettings(),
        loaded_at=datetime.now(UTC),
        agent_settings=AgentSettings(),
        limits_settings=LimitsSettings(max_checks_per_user_per_day=checks),
    )


def _build_coordinator(
    config: Config, stop_event: threading.Event | None = None, **dependencies: Any
) -> CheckCoordinator:
    """Use inert external adapters unless a scenario explicitly overrides them."""
    adapters = {"notifier_builder": lambda _cfg: [], **dependencies}
    return CheckCoordinator(config, stop_event or threading.Event(), **adapters)


def _coordinator(
    tmp_path: Path,
    *,
    checks: int = 3,
    check_counter: DailyCounter | None = None,
) -> CheckCoordinator:
    return _build_coordinator(
        _config(tmp_path, checks=checks),
        browser_factory=BrowserContext,
        inventory_synchronizer=_complete_sync,
        checks_today=check_counter,
    )


def _add(tmp_path: Path, telegram_id: int, count: int = 1) -> tuple[int, list[Any]]:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(telegram_id, UserRole.USER)
        bookings = [
            make_booking(f"{index:08d}-1111-4111-8111-111111111111")
            for index in range(1, count + 1)
        ]
        for booking in bookings:
            seed_booking(store, booking, user_id=user.user_id)
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
    run_suffix: str = "",
    **observed: Any,
) -> str | None:
    """Reconcile one upcoming observation; returns its monitoring booking id, if it has one."""
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
    observation = replace(observation, **observed)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        repository = SqliteAccountReservationRepository(store)
        repository.reconcile(
            user_id=user_id,
            run_id=f"seed-{remote_id}{run_suffix}",
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
        seed_booking(store, foreign_bookings[0], user_id=foreign_user_id)
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
        store.conn.execute("DELETE FROM bookings WHERE booking_id = ?", (booking.booking_id,))
        store.conn.commit()
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

    coordinator = _build_coordinator(
        _config(tmp_path),
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
    # Inventory sync never opens the per-check browser; each booking gets a fresh one.
    assert len(created) == len(closed) == 2


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
        seed_booking(store, second_booking, user_id=second_user.user_id)
    _seed_session(sessions, second_user.user_id)
    ran: list[int] = []

    class SecondUserMonitor:
        last_agentic_outcome = None

        def __init__(self, **kwargs: Any) -> None:
            self.history = kwargs["check_history"]


        def run_authenticated(self, booking: Any, snapshot: Any) -> CheckResult:
            ran.append(snapshot.metadata.owner_user_id)
            result = _failure(booking.booking_id)
            self.history.add(result)
            return result

    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.BookingComSearchMonitor",
        SecondUserMonitor,
    )
    coordinator = _build_coordinator(
        _config(tmp_path),
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
    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=ObservedBrowser,
        inventory_synchronizer=_complete_sync,
    )

    coordinator.run_scheduled()

    assert planned.is_set()
    assert browser_entries == 0
    assert coordinator.checks_today == {}


def test_midflight_revocation_keeps_history_but_suppresses_post_check_effects(
    tmp_path: Path, monkeypatch: Any
) -> None:
    user_id, bookings = _add(tmp_path, 101)
    history_written = threading.Event()
    revoked = threading.Event()
    pipeline_calls: list[list[CheckResult]] = []

    sessions = _session_repo(tmp_path)
    _seed_session(sessions, user_id)

    class RevocationMonitor:
        def __init__(self, **kwargs: Any) -> None:
            self.history = kwargs["check_history"]
            self.last_agentic_outcome = None


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
    coordinator = _build_coordinator(
        _config(tmp_path),
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


def test_runtime_signed_out_failure_marks_only_resolved_revision_for_reauth(
    tmp_path: Path, monkeypatch: Any
) -> None:
    sessions = _session_repo(tmp_path)
    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=BrowserContext,
        session_repository=sessions,
        inventory_synchronizer=_complete_sync,
    )
    user_id, bookings = _add(tmp_path, 101)
    _seed_session(sessions, user_id)

    class SignedOutMonitor:
        last_agentic_outcome = None

        def __init__(self, **kwargs: Any) -> None:
            self.history = kwargs["check_history"]


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


def test_stopping_refuses_new_immediate_work(tmp_path: Path) -> None:
    stop = threading.Event()
    stop.set()
    coordinator = _build_coordinator(
        _config(tmp_path),
        stop,
        browser_factory=BrowserContext,
        inventory_synchronizer=_complete_sync,
    )

    assert (
        coordinator.request_immediate(101, "booking", lambda _outcome: None)
        is ImmediateAdmission.STOPPING
    )


def test_bookings_during_post_connect_sync_joins_it_instead_of_busy(
    tmp_path: Path,
) -> None:
    _add(tmp_path, 101)
    _add(tmp_path, 202, count=0)
    entered, release = threading.Event(), threading.Event()
    calls: list[Any] = []

    def blocking_sync(store: SqliteStore, user_id: int, trigger: Any) -> SynchronizationReport:
        calls.append(trigger)
        entered.set()
        release.wait(2)
        return _complete_sync(store, user_id, trigger)

    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=lambda: nullcontext(object()),
        inventory_synchronizer=blocking_sync,
    )
    connect_done, bookings_done = threading.Event(), threading.Event()
    outcomes: list[str] = []

    assert (
        coordinator.request_inventory(
            101,
            lambda _c: (outcomes.append("connect"), connect_done.set()),
            trigger=SynchronizationTrigger.CONNECT,
        )
        is ImmediateAdmission.ACCEPTED
    )
    assert entered.wait(1)
    assert (
        coordinator.request_inventory(
            101, lambda _c: (outcomes.append("bookings"), bookings_done.set())
        )
        is ImmediateAdmission.ACCEPTED
    )
    # A different user still cannot share the browser.
    assert coordinator.request_inventory(202, lambda _c: None) is ImmediateAdmission.BUSY
    settled = threading.Event()
    assert coordinator.after_inventory_sync(101, settled.set)
    assert not coordinator.after_inventory_sync(202, lambda: None)
    assert not settled.is_set()
    release.set()
    assert connect_done.wait(1) and bookings_done.wait(1) and settled.wait(1)

    assert sorted(outcomes) == ["bookings", "connect"]
    assert calls == [SynchronizationTrigger.CONNECT]  # one browser run served both

    # Once the joined run finishes, a fresh /bookings starts a new sync.
    fresh = threading.Event()
    assert (
        coordinator.request_inventory(101, lambda _c: fresh.set())
        is ImmediateAdmission.ACCEPTED
    )
    assert fresh.wait(1)
    assert len(calls) == 2
    assert not coordinator.after_inventory_sync(101, lambda: None)


def test_revoked_user_sync_fails_closed_without_any_browser(tmp_path: Path) -> None:
    user_id, _bookings = _add(tmp_path, 101)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        SqliteUserRepository(store).set_access_state(user_id, UserAccessState.REVOKED)

    def forbidden(*_args: Any) -> Any:
        raise AssertionError("a revoked caller must not reach a browser or executor")

    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=forbidden,
        agentic_inventory_executor_factory=forbidden,
        bookings_inventory_executor_factory=forbidden,
    )
    with SqliteStore(tmp_path / "booksaver.db") as store:
        report, observed = coordinator._synchronize_user_job_uncached(  # noqa: SLF001
            store, user_id, SynchronizationTrigger.SCHEDULED,
        )

    assert observed is False
    assert report.completeness is InventoryCompleteness.FAILED
    assert report.failure_code is SynchronizationFailureCode.AUTH_REQUIRED


def test_predictable_inventory_failure_does_not_open_incident_sink(
    tmp_path: Path,
) -> None:
    _add(tmp_path, 101)

    def predictable_failure(_store: Any, _user_id: int, _trigger: Any) -> SynchronizationReport:
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

    coordinator = _build_coordinator(
        _config(tmp_path),
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


def test_check_now_synchronizes_before_resolving_booking(tmp_path: Path) -> None:
    events: list[str] = []

    def synchronize(_store: SqliteStore, _user_id: int, trigger: Any) -> SynchronizationReport:
        events.append(trigger.value)
        return _complete_sync(_store, _user_id, trigger)

    coordinator = _build_coordinator(
        _config(tmp_path),
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


def test_check_now_reuses_inventory_synchronized_within_the_last_minute(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    fail_next: list[bool] = []

    def synchronize(store: SqliteStore, user_id: int, trigger: Any) -> SynchronizationReport:
        events.append(trigger.value)
        report = _complete_sync(store, user_id, trigger)
        if fail_next and fail_next.pop():
            return replace(report, completeness=InventoryCompleteness.FAILED)
        return report

    coordinator = _build_coordinator(
        _config(tmp_path, checks=10),
        browser_factory=BrowserContext,
        inventory_synchronizer=synchronize,
    )
    now = [1000.0]
    coordinator._monotonic = lambda: now[0]
    _user_id, bookings = _add(tmp_path, 101)

    def fake_run(self: Any, store: Any, browser: Any, owner: int, booking: Any) -> CheckResult:
        events.append("price_check")
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(fake_run, coordinator)  # type: ignore[method-assign]

    def run(request: Callable[[Callable[[Any], None]], Any]) -> None:
        done = threading.Event()
        assert request(lambda _outcome: done.set()) is ImmediateAdmission.ACCEPTED
        assert done.wait(1)

    def check_now() -> None:
        run(lambda cb: coordinator.request_immediate(101, bookings[0].booking_id, cb))

    run(lambda cb: coordinator.request_inventory(
        101, cb, trigger=SynchronizationTrigger.CONNECT,
    ))
    now[0] += 59
    check_now()  # the connect sync is fresh: straight to the price check
    assert events == [SynchronizationTrigger.CONNECT.value, "price_check"]

    now[0] += 2  # 61s after the only sync
    check_now()
    assert events[2:] == [SynchronizationTrigger.CHECK_NOW.value, "price_check"]

    # A sync that raises also clears the earlier complete one.
    raise_next = [True]
    original = coordinator._synchronize_user_job_uncached

    def raising(*args: Any) -> Any:
        if raise_next and raise_next.pop():
            raise RuntimeError("browser crashed")
        return original(*args)

    coordinator._synchronize_user_job_uncached = raising  # type: ignore[method-assign]
    run(lambda cb: coordinator.request_inventory(101, cb))  # raises inside the worker
    check_now()
    assert events[4:] == [SynchronizationTrigger.CHECK_NOW.value, "price_check"]
    del events[4:]

    # A failed sync is never reused and clears the earlier complete one.
    fail_next.append(True)
    run(lambda cb: coordinator.request_inventory(101, cb))
    check_now()
    assert events[4:] == [
        SynchronizationTrigger.BOOKINGS.value,
        SynchronizationTrigger.CHECK_NOW.value,
        "price_check",
    ]


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

    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=legacy_browser_factory,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _leases: executor,
        bookings_inventory_executor_factory=lambda _leases: executor,
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


def test_bookings_uses_its_own_inventory_factory_while_other_triggers_share_one(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        users.link_telegram_id(owner.user_id, 101)
    _seed_session(sessions, owner.user_id)
    browser_use = FakeInventoryBrowserExecutor([_agentic_inventory_result()])
    other = FakeInventoryBrowserExecutor([_agentic_inventory_result()])
    legacy_browser_opens: list[None] = []

    def legacy_browser_factory() -> BrowserContext:
        legacy_browser_opens.append(None)
        return BrowserContext()

    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=legacy_browser_factory,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _leases: other,
        bookings_inventory_executor_factory=lambda _leases: browser_use,
    )

    with SqliteStore(tmp_path / "booksaver.db") as store:
        coordinator._synchronize_user_job(  # noqa: SLF001 - trigger route contract
            store,
            owner.user_id,
            SynchronizationTrigger.BOOKINGS,
        )
        coordinator._synchronize_user_job(  # noqa: SLF001 - trigger route contract
            store,
            owner.user_id,
            SynchronizationTrigger.CHECK_NOW,
        )

    assert len(browser_use.requests) == 1
    assert len(other.requests) == 1
    assert legacy_browser_opens == []


def test_undisclosed_invitee_uses_agentic_inventory_route(tmp_path: Path) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        invitee = SqliteUserRepository(store).get_or_create_by_telegram_id(202, UserRole.USER)
    _seed_session(sessions, invitee.user_id)
    executor = FakeInventoryBrowserExecutor(
        [InventoryExecutionResult(InventoryExecutionStatus.PROVIDER_FAILURE)]
    )
    legacy_opens: list[None] = []

    def legacy_browser_factory() -> BrowserContext:
        legacy_opens.append(None)
        return BrowserContext()

    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=legacy_browser_factory,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _leases: executor,
        bookings_inventory_executor_factory=lambda _leases: executor,
    )
    completed = threading.Event()

    # ADR-062: no disclosure record is needed; every active user is served by the agentic route.
    assert (
        coordinator.request_inventory(202, lambda _outcome: completed.set())
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(1)

    assert len(executor.requests) == 1
    assert legacy_opens == []


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

    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=legacy_browser_factory,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _leases: executor,
        bookings_inventory_executor_factory=lambda _leases: executor,
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

    coordinator = _build_coordinator(
        _config(tmp_path),
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
    source_booking = _future_booking("agentic-current-positive")
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
    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=BrowserContext,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _leases: executor,
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
    assert executor.requests[0].limits.max_actions == 40
    assert executor.requests[0].limits.max_computer_use_actions == 6
    assert executor.requests[0].limits.max_job_cost == UsdAmount(1_000_000)
    assert residual_limits[0] is not None
    assert residual_limits[0].deadline == executor.requests[0].limits.deadline
    assert residual_limits[0].max_actions == 15
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
    stale_source = _future_booking("agentic-stale")
    current_source = _future_booking("agentic-current")
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

    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=browser_factory,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _leases: executor,
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
    source = _future_booking("agentic-terminal-detail")
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

    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=lambda: price_browser_opens.append(None) or BrowserContext(),
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _leases: executor,
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
        seed_booking(store, booking, user_id=owner.user_id)
    _seed_session(sessions, owner.user_id)
    config = _config(tmp_path)
    executor_calls: list[None] = []
    coordinator = _build_coordinator(
        config,
        browser_factory=BrowserContext,
        session_repository=sessions,
        agentic_executor_factory=lambda _leases: executor_calls.append(None) or object(),
    )
    exhausted = AgenticBrowserJobContext(
        local_user_id=owner.user_id,
        job_kind=BrowserJobKind.CHECK_NOW,
        job_id="agentic-exhausted-shared-budget",
        deadline=datetime.now(UTC) + timedelta(minutes=3),
        job_limit_micro_usd=config.agent_settings.max_job_cost_micro_usd,
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


def test_disclosed_unqualified_invitee_uses_consented_users_agentic_price_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions = _session_repo(tmp_path)
    booking = make_booking("consented-invitee-agentic-price")
    config = _config(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        invitee = users.get_or_create_by_telegram_id(202, UserRole.USER)
        seed_booking(store, booking, user_id=invitee.user_id)
        SqliteAgenticDisclosureConsentRepository(store).acknowledge(
            user_id=invitee.user_id,
            disclosure_version=config.agentic_browser_settings.disclosure_version,
            acknowledged_at=datetime.now(UTC),
        )
    _seed_session(sessions, invitee.user_id)
    observed_routes: list[Any] = []
    executor_factory_calls: list[None] = []

    class Monitor:
        last_agentic_outcome = None

        def __init__(self, **kwargs: Any) -> None:
            self.history = kwargs["check_history"]
            observed_routes.append(kwargs["agentic_price_check"])


        def run_authenticated(self, selected: Any, _snapshot: Any) -> CheckResult:
            result = _failure(selected.booking_id)
            self.history.add(result)
            return result

    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.BookingComSearchMonitor",
        Monitor,
    )
    coordinator = _build_coordinator(
        config,
        browser_factory=BrowserContext,
        session_repository=sessions,
        agentic_executor_factory=lambda _leases: (
            executor_factory_calls.append(None) or object()
        ),
    )

    with SqliteStore(tmp_path / "booksaver.db") as store:
        qualification = SqliteAgenticQualificationRepository(store).qualification_state()
        coordinator._run_booking(  # noqa: SLF001 - price-route integration contract
            store,
            object(),
            invitee.user_id,
            booking,
        )

    assert qualification.status is QualificationStatus.UNQUALIFIED
    assert len(observed_routes) == 1
    assert observed_routes[0] is not None
    assert executor_factory_calls == [None]


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
    stale_source = _future_booking("scheduled-stale")
    current_source = _future_booking("scheduled-current")
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
    coordinator = _build_coordinator(
        _config(tmp_path, checks=10),
        browser_factory=BrowserContext,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _leases: executor,
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
    source_booking = _future_booking("scheduled-shared-residual")
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
    coordinator = _build_coordinator(
        _config(tmp_path, checks=10),
        browser_factory=BrowserContext,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _leases: executor,
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
    assert residual_limits[0].max_actions == 15
    assert residual_limits[0].max_computer_use_actions == 4
    assert residual_limits[0].max_job_cost == UsdAmount(750_000)


def test_empty_inventory_reports_for_owner_and_invitee_without_legacy_browser(
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
        [
            InventoryExecutionResult(status=InventoryExecutionStatus.EMPTY_UPCOMING),
            InventoryExecutionResult(status=InventoryExecutionStatus.EMPTY_UPCOMING),
        ]
    )
    legacy_browser_opens: list[None] = []

    def legacy_browser_factory() -> BrowserContext:
        legacy_browser_opens.append(None)
        return BrowserContext()

    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=legacy_browser_factory,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _leases: executor,
        bookings_inventory_executor_factory=lambda _leases: executor,
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

    assert all(c.report is not None and c.report.upcoming_empty_observed for c in completions)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        for user_id in (owner.user_id, invitee.user_id):
            report = SqliteAccountReservationRepository(store).latest_run_for_user(user_id)
            assert report is not None and report.upcoming_empty_observed


@pytest.mark.parametrize("kind,seconds", [
    (BrowserJobKind.CHECK_NOW, 480), (BrowserJobKind.SCHEDULED_SLOT, 480),
    (BrowserJobKind.BOOKINGS_SYNC, 300), (BrowserJobKind.QUALIFICATION, 300),
])
def test_operation_deadline_depends_on_combined_job_kind(tmp_path, kind, seconds):
    coordinator = _build_coordinator(_config(tmp_path))
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        before = datetime.now(UTC)
        with coordinator._job_scope(owner.user_id, kind):
            context = coordinator._current_agentic_job()
            assert context is not None
            after = datetime.now(UTC)
            assert before + timedelta(seconds=seconds) <= context.deadline
            assert context.deadline <= after + timedelta(seconds=seconds)
            limits = context.remaining_limits(now=after, inventory=True)
            assert limits is not None
            assert limits.timeout_seconds <= 300
            assert limits.deadline <= after + timedelta(seconds=300)


@pytest.mark.parametrize("entry", ["immediate", "scheduled", "slot"])
@pytest.mark.parametrize("stop_during", ["inventory", "price_browser_start"])
def test_shutdown_between_phases_prevents_price_dispatch(tmp_path, entry, stop_during):
    stop = threading.Event()
    opened = []
    closed = []

    class StoppingBrowser(BrowserContext):
        def __enter__(self):
            opened.append(True)
            if len(opened) == 1 and stop_during == "price_browser_start":
                stop.set()
            return object()

        def __exit__(self, *args):
            closed.append(True)

    def inventory(store, user_id, trigger):
        report = _complete_sync(store, user_id, trigger)
        if stop_during == "inventory":
            stop.set()
        return report

    coordinator = _build_coordinator(
        _config(tmp_path), stop, browser_factory=StoppingBrowser,
        inventory_synchronizer=inventory,
    )
    user_id, bookings = _add(tmp_path, 101)
    attempted = []

    def price(self, store, browser, owner, booking):
        attempted.append(booking.booking_id)
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(price, coordinator)
    completions = []
    if entry == "immediate":
        completed = threading.Event()
        assert coordinator.request_immediate(
            101, bookings[0].booking_id,
            lambda result: (completions.append(result), completed.set()),
        ) is ImmediateAdmission.ACCEPTED
        assert completed.wait(1)
        assert completions[0].kind is ImmediateCompletionKind.UNAVAILABLE
    elif entry == "scheduled":
        coordinator.run_scheduled()
    else:
        with SqliteStore(tmp_path / "booksaver.db") as store:
            coordinator._run_scheduled_user_locked(store, user_id)
    assert attempted == []
    assert len(opened) == (0 if stop_during == "inventory" else 1)
    assert len(closed) == len(opened)


@pytest.mark.parametrize("inventory_elapsed,expected_price_seconds", [(140, 180), (330, 30)])
def test_real_price_admission_starts_fixed_phase_after_long_inventory(
    tmp_path, monkeypatch, inventory_elapsed, expected_price_seconds,
):
    config = _config(tmp_path)
    user_id, bookings = _add(tmp_path, 101)
    sessions = _session_repo(tmp_path)
    _seed_session(sessions, user_id)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        SqliteAgenticDisclosureConsentRepository(store).acknowledge(
            user_id=user_id, disclosure_version=config.agentic_browser_settings.disclosure_version,
            acknowledged_at=datetime.now(UTC),
        )
    admitted = []

    class Monitor:
        last_agentic_outcome = None

        def __init__(self, **kwargs):
            admitted.append(kwargs["agentic_execution_limits"])
            self.history = kwargs["check_history"]


        def run_authenticated(self, booking, snapshot):
            assert snapshot.metadata.owner_user_id == user_id
            result = _failure(booking.booking_id)
            self.history.add(result)
            return result

    monkeypatch.setattr("booksaver.daemon.check_coordinator.BookingComSearchMonitor", Monitor)
    coordinator = _build_coordinator(
        config, session_repository=sessions,
        agentic_executor_factory=lambda leases: object(),
    )
    now = datetime.now(UTC)
    context = AgenticBrowserJobContext(
        local_user_id=user_id, job_kind=BrowserJobKind.CHECK_NOW, job_id="long-inventory-job",
        deadline=now + timedelta(seconds=360 - inventory_elapsed),
        phase_deadline=now + timedelta(seconds=180 - inventory_elapsed),
        job_limit_micro_usd=1_000_000,
        inventory_allowance=True, total_actions=29, computer_actions=2, cost_micro_usd=250_000,
    )
    with SqliteStore(tmp_path / "booksaver.db") as store:
        with coordinator._resume_agentic_job(context):
            coordinator._run_booking(store, object(), user_id, bookings[0])
    assert len(admitted) == 1
    limits = admitted[0]
    assert expected_price_seconds - 1 <= limits.timeout_seconds <= expected_price_seconds
    assert limits.deadline <= context.deadline
    assert limits.deadline <= now + timedelta(seconds=expected_price_seconds + 1)
    assert limits.max_actions == 11
    assert limits.max_computer_use_actions == 4
    assert limits.max_job_cost == UsdAmount(750_000)


def _stalled_slot(
    tmp_path: Path, coordinator: Any, monkeypatch: pytest.MonkeyPatch, **observed: Any,
) -> tuple[Callable[[], None], list[tuple[str, str]], str | None, int]:
    """One user's monitored reservation with no conclusive result, and a way to run a slot."""
    monkeypatch.setenv("BOOKSAVER_TELEGRAM_BOT_TOKEN", "token")
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.TelegramNotifier.send",
        lambda _self, subject, body: sent.append((subject, body)),
    )
    ready = MagicMock()
    ready.return_value.health = UserSessionHealth.READY
    monkeypatch.setattr(EncryptedUserSessionRepository, "status", ready)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user_id = (
            SqliteUserRepository(store).get_or_create_by_telegram_id(101, UserRole.USER).user_id
        )
    booking_id = _seed_inventory_projection(
        tmp_path, user_id=user_id, remote_id="stall-remote",
        booking=_future_booking("stall-booking"), **observed,
    )
    with SqliteStore(tmp_path / "booksaver.db") as store:
        store.conn.execute(
            "UPDATE account_reservations SET first_observed_at = ? WHERE user_id = ?",
            ((datetime.now(UTC) - timedelta(days=3)).isoformat(), user_id),
        )
        store.conn.commit()
    coordinator._run_scheduled_user_locked = MethodType(  # type: ignore[method-assign]  # noqa: SLF001
        lambda _self, _store, _user: None, coordinator,
    )

    def run_slot() -> None:
        planned_at = datetime.now(UTC) - timedelta(seconds=1)
        coordinator.run_scheduled_slot(
            _scheduled_slot(tmp_path, user_id, planned_at),
            ScheduleSettings(),
            datetime.now(UTC),
        )

    return run_slot, sent, booking_id, user_id


def _conclusive(tmp_path: Path, booking_id: str | None) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        store.conn.execute(
            "INSERT INTO check_history (check_id, booking_id, checked_at, outcome, "
            "extraction_method) VALUES (?, ?, ?, 'success', 'llm')",
            (str(uuid.uuid4()), booking_id, datetime.now(UTC).isoformat()),
        )
        store.conn.commit()


def test_stall_notice_once_then_recovery_then_a_new_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _coordinator(tmp_path)
    _run_slot, sent, booking_id, _user_id = _stalled_slot(tmp_path, coordinator, monkeypatch)

    coordinator._report_monitoring_stalls(_user_id)  # noqa: SLF001
    coordinator._report_monitoring_stalls(_user_id)  # noqa: SLF001
    assert len(sent) == 1
    assert "isn't being checked" in sent[0][0]

    # The durable record survives a restart: a new coordinator does not repeat the notice.
    restarted = _coordinator(tmp_path)
    restarted._report_monitoring_stalls(_user_id)  # noqa: SLF001
    assert len(sent) == 1

    _conclusive(tmp_path, booking_id)
    restarted._report_monitoring_stalls(_user_id)  # noqa: SLF001
    restarted._report_monitoring_stalls(_user_id)  # noqa: SLF001
    assert len(sent) == 2
    assert "being checked again" in sent[1][0]

    with SqliteStore(tmp_path / "booksaver.db") as store:
        store.conn.execute("UPDATE check_history SET checked_at = ?", (
            (datetime.now(UTC) - timedelta(days=2)).isoformat(),
        ))
        store.conn.commit()
    restarted._report_monitoring_stalls(_user_id)  # noqa: SLF001
    assert len(sent) == 3


def test_a_never_monitored_reservation_with_unknown_terms_stalls_then_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _coordinator(tmp_path)
    _run_slot, sent, booking_id, user_id = _stalled_slot(
        tmp_path, coordinator, monkeypatch, booked_total=None, refundable=None,
    )
    assert booking_id is None  # never monitored: nothing to check
    with SqliteStore(tmp_path / "booksaver.db") as store:
        store.conn.execute("UPDATE booking_sync_runs SET completeness = 'complete'")
        store.conn.commit()
        row = store.conn.execute(
            "SELECT eligibility_reasons FROM account_reservations WHERE user_id = ?", (user_id,),
        ).fetchone()
    assert {"refundability_unknown", "missing_booked_total"} <= set(json.loads(row[0]))

    coordinator._report_monitoring_stalls(user_id)  # noqa: SLF001
    coordinator._report_monitoring_stalls(user_id)  # noqa: SLF001
    assert len(sent) == 1
    assert "can't confirm this reservation's booked total or refund terms" in sent[0][1]

    # A later sync establishes the facts; the same key is now monitored and gets a result.
    booking_id = _seed_inventory_projection(
        tmp_path, user_id=user_id, remote_id="stall-remote", run_suffix="-later",
        booking=_future_booking("stall-booking"),
    )
    assert booking_id is not None
    coordinator._report_monitoring_stalls(user_id)  # noqa: SLF001
    assert len(sent) == 1  # still waiting for a conclusive result
    _conclusive(tmp_path, booking_id)
    coordinator._report_monitoring_stalls(user_id)  # noqa: SLF001
    assert [subject.split()[-1] for subject, _body in sent] == ["checked", "again"]
    with SqliteStore(tmp_path / "booksaver.db") as store:
        assert store.conn.execute(
            "SELECT COUNT(*) FROM monitoring_stall_notices"
        ).fetchone()[0] == 0


def test_a_never_monitored_non_refundable_reservation_never_stalls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _coordinator(tmp_path)
    _run_slot, sent, booking_id, user_id = _stalled_slot(
        tmp_path, coordinator, monkeypatch, booked_total=None, refundable=False,
    )
    assert booking_id is None

    coordinator._report_monitoring_stalls(user_id)  # noqa: SLF001

    assert sent == []


def test_no_stall_notice_without_a_ready_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _coordinator(tmp_path)
    _run_slot, sent, _booking_id, user_id = _stalled_slot(tmp_path, coordinator, monkeypatch)
    status = MagicMock()
    status.return_value.health = UserSessionHealth.EXPIRED
    monkeypatch.setattr(EncryptedUserSessionRepository, "status", status)

    coordinator._report_monitoring_stalls(user_id)  # noqa: SLF001

    assert sent == []


def test_failed_stall_delivery_retries_on_the_next_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _coordinator(tmp_path)
    _run_slot, sent, _booking_id, user_id = _stalled_slot(tmp_path, coordinator, monkeypatch)

    def refuse(_self: Any, _subject: str, _body: str) -> None:
        raise OSError("telegram down")

    with monkeypatch.context() as down:
        down.setattr("booksaver.daemon.check_coordinator.TelegramNotifier.send", refuse)
        coordinator._report_monitoring_stalls(user_id)  # noqa: SLF001
    assert sent == []

    coordinator._report_monitoring_stalls(user_id)  # noqa: SLF001
    assert len(sent) == 1


def test_a_failing_stall_report_cannot_strand_the_scheduled_slot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _coordinator(tmp_path)
    run_slot, sent, _booking_id, user_id = _stalled_slot(tmp_path, coordinator, monkeypatch)
    coordinator._inform_provider_change = lambda _user_id: None  # type: ignore[method-assign]  # noqa: SLF001
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.SqliteMonitoringStallRepository.list_upcoming",
        MagicMock(side_effect=sqlite3.OperationalError("broken")),
    )

    run_slot()

    with SqliteStore(tmp_path / "booksaver.db") as store:
        slots = SqliteScheduledCheckSlotRepository(store).list_for_user_date(
            user_id, datetime.now(UTC).date(),
        )
    assert slots[0].status is SlotStatus.COMPLETED
    assert sent == []


def test_a_user_is_never_told_about_another_users_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _coordinator(tmp_path)
    _run_slot, sent, _booking_id, _user_id = _stalled_slot(tmp_path, coordinator, monkeypatch)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        other = SqliteUserRepository(store).get_or_create_by_telegram_id(202, UserRole.USER).user_id

    coordinator._report_monitoring_stalls(other)  # noqa: SLF001

    assert sent == []


def test_a_result_newer_than_the_notice_reports_recovery_even_if_stalled_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _coordinator(tmp_path)
    _run_slot, sent, booking_id, user_id = _stalled_slot(tmp_path, coordinator, monkeypatch)
    coordinator._report_monitoring_stalls(user_id)  # noqa: SLF001
    two_days_ago = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    with SqliteStore(tmp_path / "booksaver.db") as store:
        store.conn.execute(
            "UPDATE monitoring_stall_notices SET notified_at = ?",
            ((datetime.now(UTC) - timedelta(days=3)).isoformat(),),
        )
        store.conn.execute(
            "INSERT INTO check_history (check_id, booking_id, checked_at, outcome, "
            "extraction_method) VALUES ('old-result', ?, ?, 'success', 'llm')",
            (booking_id, two_days_ago),
        )
        store.conn.commit()

    coordinator._report_monitoring_stalls(user_id)  # noqa: SLF001

    assert [subject.split()[-1] for subject, _body in sent] == ["checked", "again", "checked"]


@pytest.mark.parametrize(
    ("completeness", "agentic", "observed", "blocked"),
    [
        ("complete", False, True, False),
        ("failed", True, True, True),
        ("incomplete", True, True, False),  # checks what it positively observed
        ("incomplete", True, False, True),
        ("incomplete", False, True, True),  # a non-agentic incomplete sync stops its checks
    ],
)
def test_stall_reason_reflects_whether_the_latest_sync_blocks_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    completeness: str, agentic: bool, observed: bool, blocked: bool,
) -> None:
    coordinator = _coordinator(tmp_path)
    _run_slot, sent, _booking_id, user_id = _stalled_slot(tmp_path, coordinator, monkeypatch)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        store.conn.execute(
            "INSERT INTO booking_sync_runs (run_id, user_id, trigger, started_at, completed_at, "
            "completeness, discovered_count, eligible_count, ineligible_count, session_revision) "
            "VALUES ('latest', ?, 'scheduled', ?, ?, ?, 0, 0, 0, 'session')",
            (
                user_id,
                (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
                (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
                completeness,
            ),
        )
        if observed:
            store.conn.execute(
                "UPDATE account_reservations SET last_sync_run_id = 'latest' WHERE user_id = ?",
                (user_id,),
            )
        if agentic:
            store.conn.execute(
                "INSERT INTO agentic_inventory_executions (run_id, user_id, source, "
                "terminal_status, accepted_count, rejected_count, scope_count, page_count, "
                "detail_count, semantic_action_count, computer_action_count, input_tokens, "
                "output_tokens, model_cost_micro_usd, latency_ms, fallback_used, "
                "safety_codes_json) VALUES ('latest', ?, 'test', 'observed', "
                "0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '[]')",
                (user_id,),
            )
        store.conn.commit()

    coordinator._report_monitoring_stalls(user_id)  # noqa: SLF001

    assert ("can't read this reservation" in sent[0][1]) is blocked



def _inform_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, telegram_id: int = 101,
    role: UserRole = UserRole.USER, health: UserSessionHealth = UserSessionHealth.READY,
    recorded: str | None = "old-disclosure", executor: PriceExecutorKind = PriceExecutorKind.JEV,
) -> tuple[CheckCoordinator, list[tuple[str, str]], int]:
    monkeypatch.setenv("BOOKSAVER_TELEGRAM_BOT_TOKEN", "token")
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.TelegramNotifier.send",
        lambda _self, subject, body: sent.append((subject, body)),
    )
    status = MagicMock()
    status.return_value.health = health
    monkeypatch.setattr(EncryptedUserSessionRepository, "status", status)
    coordinator = _coordinator(tmp_path)
    coordinator._config.agentic_browser_settings = replace(  # noqa: SLF001
        coordinator._config.agentic_browser_settings, price_executor=executor,  # noqa: SLF001
    )
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        if role is UserRole.OWNER:
            user = users.get_owner()
            users.link_telegram_id(user.user_id, telegram_id)
        else:
            user = users.get_or_create_by_telegram_id(telegram_id, role)
        if recorded is not None:
            SqliteAgenticDisclosureConsentRepository(store).acknowledge(
                user_id=user.user_id, disclosure_version=recorded,
                acknowledged_at=datetime.now(UTC),
            )
    return coordinator, sent, user.user_id


def _recorded_version(tmp_path: Path, user_id: int) -> str | None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        record = SqliteAgenticDisclosureConsentRepository(store).get(user_id)
    return None if record is None else record.disclosure_version


@pytest.mark.parametrize("recorded", ["old-disclosure", None])
def test_invitee_is_informed_of_the_provider_change_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recorded: str | None,
) -> None:
    coordinator, sent, user_id = _inform_setup(tmp_path, monkeypatch, recorded=recorded)

    coordinator._inform_provider_change(user_id)  # noqa: SLF001

    assert len(sent) == 1
    assert "Jev" in sent[0][1]
    assert _recorded_version(tmp_path, user_id) == (
        coordinator._config.agentic_browser_settings.disclosure_version  # noqa: SLF001
    )

    coordinator._inform_provider_change(user_id)  # noqa: SLF001

    assert len(sent) == 1


def test_owner_is_never_informed_of_the_provider_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator, sent, owner_id = _inform_setup(tmp_path, monkeypatch, role=UserRole.OWNER)

    coordinator._inform_provider_change(owner_id)  # noqa: SLF001

    assert sent == []
    assert _recorded_version(tmp_path, owner_id) == "old-disclosure"


@pytest.mark.parametrize(
    "health", [h for h in UserSessionHealth if h is not UserSessionHealth.READY],
)
def test_invitee_without_a_ready_session_is_not_informed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, health: UserSessionHealth,
) -> None:
    coordinator, sent, user_id = _inform_setup(tmp_path, monkeypatch, health=health)

    coordinator._inform_provider_change(user_id)  # noqa: SLF001

    assert sent == []
    assert _recorded_version(tmp_path, user_id) == "old-disclosure"


def test_failed_provider_change_message_records_nothing_and_is_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator, sent, user_id = _inform_setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.TelegramNotifier.send",
        MagicMock(side_effect=RuntimeError("telegram down")),
    )

    coordinator._inform_provider_change(user_id)  # noqa: SLF001

    assert _recorded_version(tmp_path, user_id) == "old-disclosure"
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.TelegramNotifier.send",
        lambda _self, subject, body: sent.append((subject, body)),
    )

    coordinator._inform_provider_change(user_id)  # noqa: SLF001

    assert len(sent) == 1
    assert _recorded_version(tmp_path, user_id) != "old-disclosure"


