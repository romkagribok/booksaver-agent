from __future__ import annotations

import threading
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MethodType
from typing import Any

import pytest

from booksaver.application.ports import PageContent
from booksaver.daemon.check_coordinator import (
    CheckCoordinator,
    ImmediateAdmission,
    ImmediateCompletion,
    ImmediateCompletionKind,
    InventoryCompletion,
)
from booksaver.domain.account_sync import (
    InventoryCompleteness,
    SynchronizationReport,
    SynchronizationTrigger,
)
from booksaver.domain.agent import AgentSettings
from booksaver.domain.check_result import CheckResult, FailureCode, FailureReason
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
    NotificationSettings,
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
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(
            telegram_id, UserRole.USER
        )
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
        return SqliteScheduledCheckSlotRepository(store).insert_daily_schedule(
            (slot,)
        )[0].identity


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
        foreign_user_id = SqliteUserRepository(store).get_or_create_by_telegram_id(
            202, UserRole.USER
        ).user_id
        foreign_bookings = [make_booking("99999999-1111-4111-8111-111111111111")]
        SqliteBookingRepository(store).add(
            foreign_bookings[0], user_id=foreign_user_id
        )
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

    assert coordinator.request_immediate(
        101, bookings[0].booking_id, lambda _outcome: None
    ) is ImmediateAdmission.BUSY
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

    assert coordinator.request_immediate(
        101,
        bookings[0].booking_id,
        lambda outcome: (outcomes.append(outcome), completed.set()),
    ) is ImmediateAdmission.ACCEPTED
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

    assert coordinator.request_immediate(
        101,
        bookings[0].booking_id,
        lambda outcome: (outcomes.append(outcome), completed.set()),
    ) is ImmediateAdmission.ACCEPTED
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

    def delete_during_run(
        self: Any, store: Any, browser: Any, owner: int, booking: Any
    ) -> Any:
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
        SqliteUserRepository(store).set_access_state(
            user_id, UserAccessState.REVOKED
        )
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(  # type: ignore[method-assign]
        revoke_after_first, coordinator
    )
    coordinator.run_scheduled()

    assert len(ran) == 1
    assert coordinator.checks_today == {user_id: 1}
    unrun = next(booking for booking in bookings if booking.booking_id not in ran)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        second_history = SqliteCheckHistoryRepository(store).get_recent(
            unrun.booking_id
        )
    assert second_history == []


def test_one_users_missing_session_does_not_stop_another_users_scheduled_check(
    tmp_path: Path, monkeypatch: Any
) -> None:
    sessions = _session_repo(tmp_path)
    first_user_id, first_bookings = _add(tmp_path, 101)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        second_user = SqliteUserRepository(store).get_or_create_by_telegram_id(
            202, UserRole.USER
        )
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
        first_result = SqliteCheckHistoryRepository(store).get_recent(
            first_bookings[0].booking_id
        )[0]
        second_result = SqliteCheckHistoryRepository(store).get_recent(
            second_booking.booking_id
        )[0]
    assert first_result.failure_reason is not None
    assert first_result.failure_reason.code is FailureCode.AUTH_REQUIRED
    assert second_result.failure_reason is not None
    assert second_result.failure_reason.code is FailureCode.STEP_FAILED
    assert first_user_id != second_user.user_id


def test_revoked_plan_snapshot_never_starts_browser(
    tmp_path: Path, monkeypatch: Any
) -> None:
    user_id, _bookings = _add(tmp_path, 101)
    planned = threading.Event()
    browser_entries = 0

    def revoke_after_plan(**kwargs: Any) -> Any:
        plan = build_check_plan(**kwargs)
        with SqliteStore(tmp_path / "booksaver.db") as store:
            SqliteUserRepository(store).set_access_state(
                user_id, UserAccessState.REVOKED
            )
        planned.set()
        return plan

    class ObservedBrowser(AbstractContextManager[object]):
        def __enter__(self) -> object:
            nonlocal browser_entries
            browser_entries += 1
            return object()

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.build_check_plan", revoke_after_plan
    )
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
            SqliteUserRepository(store).set_access_state(
                user_id, UserAccessState.REVOKED
            )
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


def test_capped_notice_is_suppressed_for_revoked_user(
    tmp_path: Path, monkeypatch: Any
) -> None:
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


def test_llm_allowance_caps_monitor_then_disables_llm(
    tmp_path: Path, monkeypatch: Any
) -> None:
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

    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.BookingComSearchMonitor", FakeMonitor
    )
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
        page_text=(
            "Standard Double\n€ 350.00\nFree cancellation before 30 August 2026"
        ),
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

    assert coordinator.request_immediate(
        101, "booking", lambda _outcome: None
    ) is ImmediateAdmission.STOPPING


def test_bookings_request_discovers_and_projects_authenticated_inventory(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(
            101, UserRole.USER
        )
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

    assert coordinator.request_inventory(
        101,
        lambda outcome: (outcomes.append(outcome), completed.set()),
    ) is ImmediateAdmission.ACCEPTED
    assert completed.wait(1)

    assert outcomes[0].report is not None and outcomes[0].report.succeeded
    assert outcomes[0].reservations[0].observation.property_name == (
        "Synchronized Hotel"
    )
    with SqliteStore(tmp_path / "booksaver.db") as store:
        projected = SqliteBookingRepository(store).list_active_for_user(user.user_id)
    assert len(projected) == 1


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

    def fake_run(
        self: Any, store: Any, browser: Any, owner: int, booking: Any
    ) -> CheckResult:
        events.append("price_check")
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(fake_run, coordinator)  # type: ignore[method-assign]
    coordinator.request_immediate(
        101, bookings[0].booking_id, lambda _outcome: completed.set()
    )
    assert completed.wait(1)

    assert events == [SynchronizationTrigger.CHECK_NOW.value, "price_check"]
