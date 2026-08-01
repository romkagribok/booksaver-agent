from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum

_UTC_DAY = timedelta(days=1)


class SlotStatus(Enum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    MISSED = "missed"


class MissReason(Enum):
    GRACE_EXPIRED = "grace_expired"
    SUPERSEDED_CATCH_UP = "superseded_catch_up"
    SPACING_CONFLICT = "spacing_conflict"
    RECOVERED_RUNNING = "recovered_running"
    USER_UNAVAILABLE = "user_unavailable"
    STOPPING = "stopping"


class ScheduledAdmission(Enum):
    COMPLETED = "completed"
    BUSY = "busy"
    STOPPING = "stopping"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class ScheduleSettings:
    """Validated policy for durable per-user daily check slots."""

    checks_per_booking_per_day: int = 3
    minimum_spacing: timedelta = timedelta(hours=2)
    missed_run_grace: timedelta = timedelta(hours=1)
    retention_days: int = 30

    def __post_init__(self) -> None:
        if (
            isinstance(self.checks_per_booking_per_day, bool)
            or not isinstance(self.checks_per_booking_per_day, int)
            or self.checks_per_booking_per_day < 1
        ):
            raise ValueError("checks_per_booking_per_day must be a positive integer")
        if not isinstance(self.minimum_spacing, timedelta) or self.minimum_spacing <= timedelta(0):
            raise ValueError("minimum_spacing must be a positive duration")
        if (
            not isinstance(self.missed_run_grace, timedelta)
            or self.missed_run_grace <= timedelta(0)
        ):
            raise ValueError("missed_run_grace must be a positive duration")
        if (
            isinstance(self.retention_days, bool)
            or not isinstance(self.retention_days, int)
            or self.retention_days < 1
        ):
            raise ValueError("retention_days must be a positive integer")

        window_width = _UTC_DAY / self.checks_per_booking_per_day
        if self.minimum_spacing >= window_width:
            raise ValueError(
                "checks_per_booking_per_day and minimum_spacing must leave random range "
                "within 24 hours"
            )


@dataclass(frozen=True, slots=True)
class SlotIdentity:
    user_id: int
    schedule_date: date
    ordinal: int

    def __post_init__(self) -> None:
        if isinstance(self.schedule_date, datetime) or not isinstance(self.schedule_date, date):
            raise ValueError("schedule_date must be a date")
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int) or self.ordinal < 0:
            raise ValueError("ordinal must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ScheduledCheckSlot:
    """One durable opportunity to run a user-scoped scheduled batch."""

    identity: SlotIdentity
    planned_at: datetime
    status: SlotStatus = SlotStatus.PLANNED
    started_at: datetime | None = None
    finished_at: datetime | None = None
    miss_reason: MissReason | None = None

    def __post_init__(self) -> None:
        _require_utc("planned_at", self.planned_at)
        if self.planned_at.date() != self.identity.schedule_date:
            raise ValueError("planned_at must belong to the slot's UTC schedule_date")
        if self.started_at is not None:
            _require_utc("started_at", self.started_at)
            if self.started_at < self.planned_at:
                raise ValueError("started_at cannot precede planned_at")
        if self.finished_at is not None:
            _require_utc("finished_at", self.finished_at)
            if self.finished_at < self.planned_at:
                raise ValueError("finished_at cannot precede planned_at")
            if self.started_at is not None and self.finished_at < self.started_at:
                raise ValueError("finished_at cannot precede started_at")

        if self.status is SlotStatus.PLANNED:
            outcome_fields = (self.started_at, self.finished_at, self.miss_reason)
            if any(value is not None for value in outcome_fields):
                raise ValueError("a planned slot cannot carry lifecycle outcome fields")
        elif self.status is SlotStatus.RUNNING:
            if (
                self.started_at is None
                or self.finished_at is not None
                or self.miss_reason is not None
            ):
                raise ValueError("a running slot requires only started_at")
        elif self.status is SlotStatus.COMPLETED:
            if self.started_at is None or self.finished_at is None or self.miss_reason is not None:
                raise ValueError("a completed slot requires start and finish without a miss reason")
        elif self.status is SlotStatus.MISSED:
            if self.finished_at is None or self.miss_reason is None:
                raise ValueError("a missed slot requires finished_at and a miss reason")

    @property
    def user_id(self) -> int:
        return self.identity.user_id

    @property
    def schedule_date(self) -> date:
        return self.identity.schedule_date

    @property
    def ordinal(self) -> int:
        return self.identity.ordinal

    @property
    def is_terminal(self) -> bool:
        return self.status in {SlotStatus.COMPLETED, SlotStatus.MISSED}


def generate_daily_slots(
    user_id: int,
    schedule_date: date,
    settings: ScheduleSettings,
    *,
    randbelow: Callable[[int], int],
    prior_day_final_planned_at: datetime | None = None,
) -> tuple[ScheduledCheckSlot, ...]:
    """Generate one constrained random UTC slot inside each equal daily window.

    ``randbelow`` is injected so production can use ``SystemRandom().randrange`` while
    tests can make each draw deterministic. Each draw is over the feasible suffix of
    its window, which preserves randomness without an unbounded redraw loop.
    """

    if isinstance(schedule_date, datetime) or not isinstance(schedule_date, date):
        raise ValueError("schedule_date must be a date")

    day_start = datetime.combine(schedule_date, datetime.min.time(), tzinfo=UTC)
    if prior_day_final_planned_at is not None:
        _require_utc("prior_day_final_planned_at", prior_day_final_planned_at)
        if prior_day_final_planned_at >= day_start:
            raise ValueError("prior_day_final_planned_at must precede schedule_date")

    previous = prior_day_final_planned_at
    slots: list[ScheduledCheckSlot] = []
    count = settings.checks_per_booking_per_day

    for ordinal in range(count):
        window_start = day_start + (_UTC_DAY * ordinal / count)
        window_end = (
            day_start + _UTC_DAY
            if ordinal == count - 1
            else day_start + (_UTC_DAY * (ordinal + 1) / count)
        )
        feasible_start = window_start
        if previous is not None:
            feasible_start = max(feasible_start, previous + settings.minimum_spacing)

        span_seconds = int((window_end - feasible_start).total_seconds())
        if span_seconds <= 0:
            raise ValueError(
                "schedule settings leave no whole-second random range in a slot window"
            )

        offset_seconds = randbelow(span_seconds)
        if (
            isinstance(offset_seconds, bool)
            or not isinstance(offset_seconds, int)
            or not 0 <= offset_seconds < span_seconds
        ):
            raise ValueError("randbelow must return an integer in [0, upper_bound)")

        planned_at = feasible_start + timedelta(seconds=offset_seconds)
        slot = ScheduledCheckSlot(
            identity=SlotIdentity(
                user_id=user_id,
                schedule_date=schedule_date,
                ordinal=ordinal,
            ),
            planned_at=planned_at,
        )
        slots.append(slot)
        previous = planned_at

    return tuple(slots)


def _require_utc(field_name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be a timezone-aware UTC datetime")
