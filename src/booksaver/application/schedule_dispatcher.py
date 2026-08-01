from __future__ import annotations

import logging
import secrets
import threading
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol

from booksaver.domain.schedule import (
    ScheduledAdmission,
    ScheduledCheckSlot,
    ScheduleSettings,
    SlotIdentity,
    generate_daily_slots,
)

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]
RandomBelow = Callable[[int], int]
ActiveUserIds = Callable[[], Sequence[int]]

_BUSY_RETRY = timedelta(seconds=30)


class ScheduledSlotRepository(Protocol):
    def list_for_user_date(
        self, user_id: int, schedule_date: date
    ) -> tuple[ScheduledCheckSlot, ...]: ...

    def insert_daily_schedule(
        self, slots: Sequence[ScheduledCheckSlot]
    ) -> tuple[ScheduledCheckSlot, ...]: ...

    def last_planned_before(self, user_id: int, instant: datetime) -> ScheduledCheckSlot | None: ...

    def recover_running(self, now: datetime) -> int: ...

    def prepare_due(
        self,
        now: datetime,
        grace: timedelta,
        minimum_spacing: timedelta,
    ) -> tuple[ScheduledCheckSlot, ...]: ...

    def next_planned_at(self, now: datetime) -> datetime | None: ...

    def prune_terminal(self, before: datetime) -> int: ...


RepositoryFactory = Callable[[], AbstractContextManager[ScheduledSlotRepository]]


class ScheduledCoordinator(Protocol):
    def run_scheduled_slot(
        self,
        identity: SlotIdentity,
        settings: ScheduleSettings,
        now: datetime,
    ) -> ScheduledAdmission: ...


class RandomizedScheduleDispatcher:
    """Plan, recover, and dispatch durable per-user randomized daily slots."""

    def __init__(
        self,
        *,
        settings: ScheduleSettings,
        repository_factory: RepositoryFactory,
        active_user_ids: ActiveUserIds,
        coordinator: ScheduledCoordinator,
        stop_event: threading.Event,
        randbelow: RandomBelow = secrets.randbelow,
        clock: Clock | None = None,
    ) -> None:
        self._settings = settings
        self._repository_factory = repository_factory
        self._active_user_ids = active_user_ids
        self._coordinator = coordinator
        self._stop_event = stop_event
        self._randbelow = randbelow
        self._clock = clock or (lambda: datetime.now(UTC))
        self._recovery_complete = False
        self._last_pruned_on: date | None = None

    def run_once(self) -> datetime | None:
        """Run one adaptive pass and return the next desired UTC wake."""
        if self._stop_event.is_set():
            return None
        now = self._utc_now()
        active_user_ids = tuple(sorted(set(self._active_user_ids())))

        with self._repository_factory() as repository:
            self._ensure_horizon(repository, active_user_ids, now.date())
            if not self._recovery_complete:
                repository.recover_running(now)
                self._recovery_complete = True
            if self._last_pruned_on != now.date():
                repository.prune_terminal(now - timedelta(days=self._settings.retention_days))
                self._last_pruned_on = now.date()
            due = repository.prepare_due(
                now,
                self._settings.missed_run_grace,
                self._settings.minimum_spacing,
            )

            for slot in sorted(
                due,
                key=lambda candidate: (
                    candidate.planned_at,
                    candidate.user_id,
                    candidate.ordinal,
                ),
            ):
                if self._stop_event.is_set():
                    return None
                dispatch_at = self._utc_now()
                admission = self._coordinator.run_scheduled_slot(
                    slot.identity,
                    self._settings,
                    dispatch_at,
                )
                logger.info(
                    "Scheduled slot dispatch result "
                    "(user_id=%s, date=%s, ordinal=%s, planned_at=%s, "
                    "lateness_seconds=%d, outcome=%s)",
                    slot.user_id,
                    slot.schedule_date,
                    slot.ordinal,
                    slot.planned_at.isoformat(),
                    max(0, int((dispatch_at - slot.planned_at).total_seconds())),
                    admission.value,
                )
                if admission is ScheduledAdmission.BUSY:
                    retry_at = self._utc_now() + _BUSY_RETRY
                    logger.info(
                        "Scheduled slot deferred because coordinator is busy "
                        "(user_id=%s, date=%s, ordinal=%s, retry_at=%s)",
                        slot.user_id,
                        slot.schedule_date,
                        slot.ordinal,
                        retry_at.isoformat(),
                    )
                    return retry_at
                if admission is ScheduledAdmission.STOPPING:
                    return None

            return repository.next_planned_at(self._utc_now())

    def _ensure_horizon(
        self,
        repository: ScheduledSlotRepository,
        user_ids: Sequence[int],
        today: date,
    ) -> None:
        tomorrow = today + timedelta(days=1)
        for user_id in user_ids:
            for schedule_date in (today, tomorrow):
                if repository.list_for_user_date(user_id, schedule_date):
                    continue
                day_start = datetime.combine(schedule_date, time.min, tzinfo=UTC)
                prior = repository.last_planned_before(user_id, day_start)
                slots = generate_daily_slots(
                    user_id,
                    schedule_date,
                    self._settings,
                    randbelow=self._randbelow,
                    prior_day_final_planned_at=(prior.planned_at if prior is not None else None),
                )
                persisted = repository.insert_daily_schedule(slots)
                logger.info(
                    "Daily check schedule available (user_id=%s, date=%s, slots=%d)",
                    user_id,
                    schedule_date,
                    len(persisted),
                )

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("dispatcher clock must return a timezone-aware datetime")
        return value.astimezone(UTC)
