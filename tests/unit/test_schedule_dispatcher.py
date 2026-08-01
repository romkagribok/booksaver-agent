from __future__ import annotations

import threading
from collections.abc import Sequence
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta

import pytest

from booksaver.application.schedule_dispatcher import RandomizedScheduleDispatcher
from booksaver.domain.schedule import (
    ScheduledAdmission,
    ScheduledCheckSlot,
    ScheduleSettings,
    SlotIdentity,
    SlotStatus,
)

NOW = datetime(2026, 8, 1, 12, tzinfo=UTC)
SETTINGS = ScheduleSettings()


def _slot(
    user_id: int,
    ordinal: int,
    planned_at: datetime,
    *,
    schedule_date: date | None = None,
) -> ScheduledCheckSlot:
    return ScheduledCheckSlot(
        identity=SlotIdentity(
            user_id=user_id,
            schedule_date=schedule_date or planned_at.date(),
            ordinal=ordinal,
        ),
        planned_at=planned_at,
        status=SlotStatus.PLANNED,
    )


class FakeRepository:
    def __init__(self, *, due: Sequence[ScheduledCheckSlot] = ()) -> None:
        self.schedules: dict[tuple[int, date], tuple[ScheduledCheckSlot, ...]] = {}
        self.due = tuple(due)
        self.recover_calls: list[datetime] = []
        self.prepare_calls: list[tuple[datetime, timedelta, timedelta]] = []
        self.prune_calls: list[datetime] = []
        self.next_wake: datetime | None = NOW + timedelta(hours=2)
        self.insert_calls: list[tuple[ScheduledCheckSlot, ...]] = []

    def list_for_user_date(
        self, user_id: int, schedule_date: date
    ) -> tuple[ScheduledCheckSlot, ...]:
        return self.schedules.get((user_id, schedule_date), ())

    def insert_daily_schedule(
        self, slots: Sequence[ScheduledCheckSlot]
    ) -> tuple[ScheduledCheckSlot, ...]:
        value = tuple(slots)
        self.insert_calls.append(value)
        if value:
            key = (value[0].user_id, value[0].schedule_date)
            self.schedules.setdefault(key, value)
            return self.schedules[key]
        return ()

    def last_planned_before(self, user_id: int, instant: datetime) -> ScheduledCheckSlot | None:
        candidates = [
            slot
            for (candidate_user_id, _), slots in self.schedules.items()
            if candidate_user_id == user_id
            for slot in slots
            if slot.planned_at < instant
        ]
        return max(candidates, key=lambda slot: slot.planned_at, default=None)

    def recover_running(self, now: datetime) -> int:
        self.recover_calls.append(now)
        return 0

    def prepare_due(
        self,
        now: datetime,
        grace: timedelta,
        minimum_spacing: timedelta,
    ) -> tuple[ScheduledCheckSlot, ...]:
        self.prepare_calls.append((now, grace, minimum_spacing))
        return self.due

    def next_planned_at(self, now: datetime) -> datetime | None:
        return self.next_wake

    def prune_terminal(self, before: datetime) -> int:
        self.prune_calls.append(before)
        return 0


class FakeCoordinator:
    def __init__(
        self,
        admissions: Sequence[ScheduledAdmission] = (),
    ) -> None:
        self._admissions = list(admissions)
        self.calls: list[tuple[SlotIdentity, ScheduleSettings, datetime]] = []

    def run_scheduled_slot(
        self,
        identity: SlotIdentity,
        settings: ScheduleSettings,
        now: datetime,
    ) -> ScheduledAdmission:
        self.calls.append((identity, settings, now))
        if self._admissions:
            return self._admissions.pop(0)
        return ScheduledAdmission.COMPLETED


def _dispatcher(
    repository: FakeRepository,
    coordinator: FakeCoordinator,
    *,
    active_users: Sequence[int] = (2, 1),
    stop_event: threading.Event | None = None,
    clock: datetime = NOW,
) -> RandomizedScheduleDispatcher:
    return RandomizedScheduleDispatcher(
        settings=SETTINGS,
        repository_factory=lambda: nullcontext(repository),
        active_user_ids=lambda: active_users,
        coordinator=coordinator,
        stop_event=stop_event or threading.Event(),
        randbelow=lambda upper: upper // 2,
        clock=lambda: clock,
    )


def test_plans_current_and_next_dates_once_for_each_active_user() -> None:
    repository = FakeRepository()
    dispatcher = _dispatcher(repository, FakeCoordinator(), active_users=(2, 1, 2))

    dispatcher.run_once()
    dispatcher.run_once()

    assert sorted(repository.schedules) == [
        (1, date(2026, 8, 1)),
        (1, date(2026, 8, 2)),
        (2, date(2026, 8, 1)),
        (2, date(2026, 8, 2)),
    ]
    assert len(repository.insert_calls) == 4
    assert all(len(slots) == 3 for slots in repository.insert_calls)


def test_restart_recovery_runs_once_but_due_preparation_runs_each_pass() -> None:
    repository = FakeRepository()
    dispatcher = _dispatcher(repository, FakeCoordinator())

    dispatcher.run_once()
    dispatcher.run_once()

    assert repository.recover_calls == [NOW]
    assert repository.prepare_calls == [
        (NOW, timedelta(hours=1), timedelta(hours=2)),
        (NOW, timedelta(hours=1), timedelta(hours=2)),
    ]
    assert repository.prune_calls == [NOW - timedelta(days=30)]


def test_due_slots_are_dispatched_in_stable_order() -> None:
    later = _slot(1, 1, NOW - timedelta(minutes=5))
    same_time_higher_user = _slot(8, 0, NOW - timedelta(minutes=10))
    same_time_lower_user = _slot(3, 2, NOW - timedelta(minutes=10))
    repository = FakeRepository(due=(later, same_time_higher_user, same_time_lower_user))
    coordinator = FakeCoordinator()

    wake = _dispatcher(repository, coordinator, active_users=()).run_once()

    assert [call[0] for call in coordinator.calls] == [
        same_time_lower_user.identity,
        same_time_higher_user.identity,
        later.identity,
    ]
    assert wake == repository.next_wake


def test_busy_slot_stays_unclaimed_and_stops_pass_with_30_second_retry() -> None:
    first = _slot(1, 0, NOW - timedelta(minutes=1))
    second = _slot(2, 0, NOW)
    repository = FakeRepository(due=(first, second))
    coordinator = FakeCoordinator((ScheduledAdmission.BUSY,))

    wake = _dispatcher(repository, coordinator, active_users=()).run_once()

    assert [call[0] for call in coordinator.calls] == [first.identity]
    assert wake == NOW + timedelta(seconds=30)


def test_stopping_admission_aborts_without_dispatching_later_slots() -> None:
    first = _slot(1, 0, NOW - timedelta(minutes=1))
    second = _slot(2, 0, NOW)
    repository = FakeRepository(due=(first, second))
    coordinator = FakeCoordinator((ScheduledAdmission.STOPPING,))

    wake = _dispatcher(repository, coordinator, active_users=()).run_once()

    assert [call[0] for call in coordinator.calls] == [first.identity]
    assert wake is None


def test_stop_event_prevents_any_new_admission() -> None:
    stop_event = threading.Event()
    stop_event.set()
    repository = FakeRepository(due=(_slot(1, 0, NOW),))
    coordinator = FakeCoordinator()

    wake = _dispatcher(
        repository,
        coordinator,
        active_users=(),
        stop_event=stop_event,
    ).run_once()

    assert coordinator.calls == []
    assert wake is None
    assert repository.insert_calls == []
    assert repository.prepare_calls == []


def test_completed_and_stale_admissions_do_not_block_later_due_users() -> None:
    first = _slot(1, 0, NOW - timedelta(minutes=2))
    second = _slot(2, 0, NOW - timedelta(minutes=1))
    repository = FakeRepository(due=(first, second))
    coordinator = FakeCoordinator((ScheduledAdmission.STALE, ScheduledAdmission.COMPLETED))

    _dispatcher(repository, coordinator, active_users=()).run_once()

    assert [call[0] for call in coordinator.calls] == [
        first.identity,
        second.identity,
    ]


def test_dispatcher_passes_settings_and_fresh_utc_time_to_coordinator() -> None:
    due = _slot(1, 0, NOW)
    repository = FakeRepository(due=(due,))
    coordinator = FakeCoordinator()

    _dispatcher(repository, coordinator, active_users=()).run_once()

    assert coordinator.calls == [(due.identity, SETTINGS, NOW)]


def test_naive_clock_fails_closed_before_touching_dependencies() -> None:
    repository = FakeRepository()
    coordinator = FakeCoordinator()
    dispatcher = _dispatcher(
        repository,
        coordinator,
        clock=datetime(2026, 8, 1, 12),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        dispatcher.run_once()

    assert repository.insert_calls == []
    assert coordinator.calls == []
