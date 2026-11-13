"""Intent 041: the silent desktop reading after a scheduled slot."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any

import pytest

from booksaver.application.browser_executor import InMemorySessionLeaseBroker
from booksaver.application.user_sessions import AuthenticatedSessionProvider
from booksaver.daemon.desktop_trial import READING_SECONDS, run_desktop_trial
from booksaver.domain.browser_executor import (
    PriceExecutionRequest,
    PriceExecutionResult,
    PriceExecutionStatus,
)
from booksaver.domain.check_result import CheckResult, FailureCode, FailureReason
from booksaver.domain.mobile_web import DesktopTrialSettings
from booksaver.domain.price_comparison import JevComparisonSettings
from booksaver.domain.schedule import ScheduledAdmission, ScheduleSettings
from booksaver.domain.user import UserRole
from booksaver.infrastructure.browser.browser_use_runtime import BrowserUseSessionHost
from booksaver.infrastructure.browser.jev_primary_executor import JevPrimaryPriceExecutor
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteStore,
    SqliteUserRepository,
    _delete_booking_rows,
)
from tests.support.bookings import seed_booking
from tests.unit.daemon.test_check_coordinator import (
    BrowserContext,
    _add,
    _build_coordinator,
    _complete_sync,
    _config,
    _failure,
    _scheduled_slot,
    _seed_session,
    _session_repo,
)
from tests.unit.daemon.test_jev_price_path import FakeJevExecutor
from tests.unit.monitor.fakes import make_booking

_TABLES = ("check_history", "check_traces", "savings_opportunities", "jev_price_runs")


def _readings(tmp_path: Path) -> list[tuple[Any, ...]]:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        return [
            tuple(row)
            for row in store.conn.execute(
                "SELECT check_id, booking_id, outcome, failure_code, live_amount, live_currency "
                "FROM desktop_trial_readings ORDER BY observed_at"
            )
        ]


def _trial(
    tmp_path: Path,
    factory: Any,
    *,
    mobile_code: FailureCode = FailureCode.STEP_FAILED,
    stop: bool = False,
    seed_session: bool = True,
) -> tuple[list[CheckResult], Any]:
    """Run the trial for two of the owner's bookings whose mobile checks just ended."""
    sessions = _session_repo(tmp_path)
    stop_event = threading.Event()
    if stop:
        stop_event.set()
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        assert owner is not None
        if seed_session:
            _seed_session(sessions, owner.user_id)
        bookings = [make_booking(f"0000000{n}-1111-4111-8111-111111111111") for n in (1, 2)]
        mobile = []
        for booking in bookings:
            seed_booking(store, booking, user_id=owner.user_id)
            mobile.append(
                CheckResult.failure(
                    booking.booking_id, datetime.now(UTC), FailureReason(mobile_code, "mobile")
                )
            )
        run_desktop_trial(
            store=store,
            executor_factory=factory,
            sessions=AuthenticatedSessionProvider(users, sessions),
            user_id=owner.user_id,
            checked=list(zip(bookings, mobile, strict=True)),
            stop_event=stop_event,
        )
    return mobile, sessions.resolve(owner.user_id).snapshot


def test_a_reading_is_stored_per_checked_booking_and_nothing_else_changes(
    tmp_path: Path,
) -> None:
    executors: list[FakeJevExecutor] = []

    class RefreshingJev(FakeJevExecutor):
        def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
            result = super().execute(request)
            self.broker.store_verified_refresh(request.session_lease, b'[{"name":"new"}]')
            return replace(result, refreshed_session_eligible=True)

    def factory(broker: InMemorySessionLeaseBroker) -> RefreshingJev:
        executors.append(RefreshingJev(broker, total="371.50"))
        return executors[-1]

    mobile, session = _trial(tmp_path, factory)

    assert _readings(tmp_path) == [
        (check.check_id, check.booking_id, "success", None, "371.50", "EUR") for check in mobile
    ]
    assert session is not None and session.cookies == b"[]"  # a refresh is never written
    limits = executors[0].requests[0].limits
    assert limits.timeout_seconds == READING_SECONDS
    assert limits.deadline - datetime.now(UTC) <= timedelta(seconds=READING_SECONDS)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        for table in _TABLES:
            assert store.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (PriceExecutionStatus.SIGNED_OUT, FailureCode.AUTH_REQUIRED),
        (PriceExecutionStatus.BOT_WALL, FailureCode.BOT_WALL),
    ],
)
def test_a_sign_out_or_bot_wall_ends_the_slots_readings(
    tmp_path: Path, status: PriceExecutionStatus, code: FailureCode
) -> None:
    calls: list[PriceExecutionRequest] = []

    class Blocked:
        def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
            calls.append(request)
            return PriceExecutionResult(status)

    mobile, _ = _trial(tmp_path, lambda _broker: Blocked())

    assert len(calls) == 1
    assert _readings(tmp_path) == [
        (mobile[0].check_id, mobile[0].booking_id, "failure", code.value, None, None)
    ]


def test_a_budget_refusal_is_stored_and_the_next_booking_is_still_read(tmp_path: Path) -> None:
    class Refused:
        def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
            return PriceExecutionResult(PriceExecutionStatus.BUDGET_EXHAUSTED)

    _trial(tmp_path, lambda _broker: Refused())

    assert [row[2:4] for row in _readings(tmp_path)] == [
        ("failure", FailureCode.BUDGET_EXCEEDED.value)
    ] * 2


@pytest.mark.parametrize(
    "scenario",
    [
        {"mobile_code": FailureCode.AUTH_REQUIRED},
        {"stop": True},
        {"seed_session": False},
    ],
)
def test_no_reading_without_a_usable_session_or_while_stopping(
    tmp_path: Path, scenario: dict[str, Any]
) -> None:
    def factory(_broker: InMemorySessionLeaseBroker) -> Any:
        raise AssertionError("no desktop browser may start")

    _trial(tmp_path, factory, **scenario)

    assert _readings(tmp_path) == []


def test_a_failing_reading_never_raises_into_the_slot(tmp_path: Path, caplog: Any) -> None:
    def factory(_broker: InMemorySessionLeaseBroker) -> Any:
        raise RuntimeError("browser exploded")

    _trial(tmp_path, factory)

    assert _readings(tmp_path) == []
    assert "Desktop trial reading failed" in caplog.text


def _trial_slot(tmp_path: Path, monkeypatch: Any, *, ends_on: date, trial_user: bool) -> Any:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.run_desktop_trial", lambda **kw: calls.append(kw)
    )
    user_id, bookings = _add(tmp_path, 101, count=2)
    config = replace(
        _config(tmp_path, checks=10),
        desktop_trial_settings=DesktopTrialSettings(
            user_ids=frozenset({user_id if trial_user else user_id + 50}), ends_on=ends_on
        ),
    )
    coordinator = _build_coordinator(
        config,
        browser_factory=BrowserContext,
        inventory_synchronizer=_complete_sync,
        desktop_trial_executor_factory=lambda _broker: None,  # type: ignore[arg-type,return-value]
    )
    order: list[str] = []

    def fake_run(self: Any, store: Any, browser: Any, owner: int, booking: Any) -> Any:
        assert not calls  # readings start only after every normal check
        order.append(booking.booking_id)
        return _failure(booking.booking_id)

    coordinator._run_booking = MethodType(fake_run, coordinator)  # type: ignore[method-assign]
    planned_at = datetime.now(UTC) - timedelta(seconds=1)
    admission = coordinator.run_scheduled_slot(
        _scheduled_slot(tmp_path, user_id, planned_at), ScheduleSettings(), datetime.now(UTC)
    )
    assert admission is ScheduledAdmission.COMPLETED
    assert len(order) == len(bookings)
    assert coordinator.checks_today == {user_id: 2}  # a reading is not a check
    return SimpleNamespace(calls=calls, user_id=user_id, order=order)


def test_slot_hands_its_checked_bookings_to_the_trial_for_a_trial_user(
    tmp_path: Path, monkeypatch: Any
) -> None:
    tomorrow = datetime.now(UTC).date() + timedelta(days=1)
    slot = _trial_slot(tmp_path, monkeypatch, ends_on=tomorrow, trial_user=True)
    assert len(slot.calls) == 1 and slot.calls[0]["user_id"] == slot.user_id
    assert [booking.booking_id for booking, _ in slot.calls[0]["checked"]] == slot.order
    assert all(result.failure_reason is not None for _, result in slot.calls[0]["checked"])


@pytest.mark.parametrize(("days_left", "trial_user"), [(0, True), (1, False)])
def test_no_trial_after_the_end_date_or_for_another_user(
    tmp_path: Path, monkeypatch: Any, days_left: int, trial_user: bool
) -> None:
    ends_on = datetime.now(UTC).date() + timedelta(days=days_left)
    assert not _trial_slot(tmp_path, monkeypatch, ends_on=ends_on, trial_user=trial_user).calls


def test_readings_are_deleted_with_their_booking_or_user(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        invitee = users.get_or_create_by_telegram_id(303, UserRole.USER)
        owner = users.get_owner()
        assert owner is not None
        for check_id, user_id, booking_id in (
            ("c-1", owner.user_id, "booking-owner"),
            ("c-2", invitee.user_id, "booking-invitee"),
        ):
            store.conn.execute(
                "INSERT INTO desktop_trial_readings (check_id, user_id, booking_id, observed_at, "
                "outcome) VALUES (?, ?, ?, '2026-11-13T00:00:00+00:00', 'failure')",
                (check_id, user_id, booking_id),
            )
        _delete_booking_rows(store.conn, "booking-owner")
        users.purge(invitee.user_id)
        assert store.conn.execute("SELECT COUNT(*) FROM desktop_trial_readings").fetchone()[0] == 0


def test_trial_executor_is_capped_at_half_tagged_and_never_refreshes_the_session(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from booksaver.cli import commands
    from booksaver.domain.mobile_web import MobileProfileId
    from booksaver.infrastructure.browser import jev_primary_executor

    built: list[dict[str, Any]] = []
    monkeypatch.setattr(
        jev_primary_executor, "LocalJevPriceExecutor", lambda **kw: built.append(kw) or "local"
    )
    config = _config(tmp_path)
    monkeypatch.delenv("BOOKSAVER_TYPESAFE_API_KEY", raising=False)
    trial = replace(
        config,
        desktop_trial_settings=DesktopTrialSettings(
            user_ids=frozenset({4}), ends_on=date(2026, 11, 20)
        ),
    )
    assert commands._make_desktop_trial_executor_factory(trial) is None  # no key
    monkeypatch.setenv("BOOKSAVER_TYPESAFE_API_KEY", "test-key")
    assert commands._make_desktop_trial_executor_factory(config) is None  # trial not configured

    executor = commands._make_desktop_trial_executor_factory(trial)(InMemorySessionLeaseBroker())

    assert isinstance(executor, JevPrimaryPriceExecutor)
    assert executor._adapter == "jev-price-desktop-trial"
    assert executor._settings.max_daily_cost_nano_usd == (
        JevComparisonSettings().max_daily_cost_nano_usd // 2
    )
    assert executor._executor_factory(InMemorySessionLeaseBroker(), 7) == "local"
    assert built[0]["allow_session_refresh"] is False and built[0]["max_cost_nano_usd"] == 7
    assert built[0]["mobile_settings"].profile_id is MobileProfileId.DESKTOP_CHROMIUM_TRIAL


class _Cdp:
    """Record `cdp.send.<Domain>.<method>(params=..., session_id=...)` calls."""

    def __init__(self, calls: dict[str, dict[str, Any]], path: str = "") -> None:
        self._calls, self._path = calls, path

    def __getattr__(self, name: str) -> _Cdp:
        return _Cdp(self._calls, f"{self._path}.{name}".lstrip("."))

    async def __call__(self, *, params: dict[str, Any], session_id: str) -> None:
        self._calls[self._path] = params


@pytest.mark.parametrize(
    ("mobile", "platform", "orientation"),
    [(True, "Android", "portraitPrimary"), (False, "Win32", "landscapePrimary")],
)
def test_browser_emulation_follows_the_profile(
    mobile: bool, platform: str, orientation: str
) -> None:
    calls: dict[str, dict[str, Any]] = {}

    async def cdp_session(_target_id: str, *, focus: bool) -> Any:
        return SimpleNamespace(cdp_client=_Cdp(calls), session_id="s-1")

    session = SimpleNamespace(
        get_page_targets=lambda: [SimpleNamespace(target_id="t-1")],
        get_or_create_cdp_session=cdp_session,
    )
    asyncio.run(
        BrowserUseSessionHost()._install_mobile_emulation(
            session,
            viewport={"width": 1280, "height": 720},
            device_scale_factor=1.0,
            user_agent="ua",
            mobile=mobile,
        )
    )
    metrics = calls["send.Emulation.setDeviceMetricsOverride"]
    assert metrics["mobile"] is mobile and metrics["screenOrientation"]["type"] == orientation
    assert ("send.Emulation.setTouchEmulationEnabled" in calls) is mobile
    assert calls["send.Network.setUserAgentOverride"]["platform"] == platform
