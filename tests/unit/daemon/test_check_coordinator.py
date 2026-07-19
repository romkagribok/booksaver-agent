from __future__ import annotations

import threading
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from types import MethodType
from typing import Any

from booksaver.daemon.check_coordinator import (
    CheckCoordinator,
    ImmediateAdmission,
    ImmediateCompletion,
    ImmediateCompletionKind,
)
from booksaver.domain.agent import AgentSettings
from booksaver.domain.check_result import CheckResult, FailureCode, FailureReason
from booksaver.domain.models import Config
from booksaver.domain.user import UserAccessState, UserRole
from booksaver.domain.value_objects import (
    CheckInterval,
    DataDirectory,
    LimitsSettings,
    NotificationSettings,
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


def test_revoked_plan_snapshot_never_starts_browser(
    tmp_path: Path, monkeypatch: Any
) -> None:
    user_id, _bookings = _add(tmp_path, 101)
    planned = threading.Event()
    browser_entered = threading.Event()

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
            browser_entered.set()
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
    )

    coordinator.run_scheduled()

    assert planned.is_set()
    assert not browser_entered.is_set()
    assert coordinator.checks_today == {}


def test_midflight_revocation_keeps_history_but_suppresses_post_check_effects(
    tmp_path: Path, monkeypatch: Any
) -> None:
    user_id, bookings = _add(tmp_path, 101)
    history_written = threading.Event()
    revoked = threading.Event()
    pipeline_calls: list[list[CheckResult]] = []
    invalid_key_calls: list[list[CheckResult]] = []

    class RevocationMonitor:
        def __init__(self, **kwargs: Any) -> None:
            self.history = kwargs["check_history"]
            self.last_llm_calls_used = 0

        def set_llm_enabled(self, enabled: bool) -> None:
            return None

        def run_all_active(self, bookings: list[Any]) -> list[CheckResult]:
            result = _failure(bookings[0].booking_id)
            self.history.add(result)
            history_written.set()
            assert revoked.wait(2)
            return [result]

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

        def run_all_active(self, bookings: list[Any]) -> list[CheckResult]:
            observed.append((self.settings.max_llm_calls, self.enabled))
            self.last_llm_calls_used = self.settings.max_llm_calls if self.enabled else 0
            result = _failure(bookings[0].booking_id)
            self.history.add(result)
            return [result]

    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.BookingComSearchMonitor", FakeMonitor
    )
    with SqliteStore(tmp_path / "booksaver.db") as store:
        coordinator._run_booking(store, object(), user_id, bookings[0])
        coordinator._run_booking(store, object(), user_id, bookings[0])

    assert observed == [(2, True), (4, False)]
    assert coordinator.llm_calls_today[user_id] == 5


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
    coordinator = CheckCoordinator(
        cfg,
        threading.Event(),
        llm_factory_builder=lambda _cfg, _store: NullLLMFactory(),
        notifier_builder=lambda _cfg: [],
        invalid_key_notifier=lambda _repo, _results: None,
        browser_factory=lambda: ExistingBrowserContext(browser),
    )
    _user_id, bookings = _add(tmp_path, 101)

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
    )

    assert coordinator.request_immediate(
        101, "booking", lambda _outcome: None
    ) is ImmediateAdmission.STOPPING
