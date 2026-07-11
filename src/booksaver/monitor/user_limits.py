from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from booksaver.domain.models import Booking
from booksaver.domain.user import User

Clock = Callable[[], datetime]


class DailyCounter:
    """In-memory per-key counter that resets at UTC midnight (US-031).

    Lives for the lifetime of the daemon process; a restart loses today's
    counts. That's an accepted trade-off, not an oversight — these are safety
    nets against runaway usage, not billing-grade accounting, and a restart
    already interrupts any in-flight checks (ADR-003, stdlib-first: no extra
    dependency or schema bump just to persist a rough daily counter across
    restarts). A small counter table would be a clean additive follow-up if
    daemon uptime turns out to be too short for this to hold in practice.
    """

    def __init__(self, clock: Clock = lambda: datetime.now(UTC)) -> None:
        self._clock = clock
        self._day: date = self._clock().date()
        self._counts: dict[int, int] = {}

    def _maybe_roll(self) -> None:
        today = self._clock().date()
        if today != self._day:
            self._day = today
            self._counts = {}

    def increment(self, key: int, by: int = 1) -> int:
        self._maybe_roll()
        self._counts[key] = self._counts.get(key, 0) + by
        return self._counts[key]

    def count(self, key: int) -> int:
        self._maybe_roll()
        return self._counts.get(key, 0)

    def snapshot(self) -> dict[int, int]:
        self._maybe_roll()
        return dict(self._counts)


@dataclass(frozen=True)
class CheckPlan:
    """A fair per-tick check order (US-031).

    `ordered` interleaves bookings round-robin across users — user A's 2nd
    booking is checked before user B's 3rd — so one user's many (or slow)
    bookings can't push another user's checks to the back of every tick.
    Users already at today's check ceiling are excluded entirely and listed
    in `capped_user_ids` so the caller can log/notify.
    """

    ordered: list[tuple[int, Booking]]
    capped_user_ids: list[int]


def build_check_plan(
    users: Sequence[User],
    bookings_by_user: Mapping[int, Sequence[Booking]],
    checks_today: Mapping[int, int],
    max_checks_per_user_per_day: int,
) -> CheckPlan:
    eligible: list[int] = []
    capped: list[int] = []
    queues: dict[int, list[Booking]] = {}

    for user in users:
        bookings = list(bookings_by_user.get(user.user_id, ()))
        if not bookings:
            continue
        if checks_today.get(user.user_id, 0) >= max_checks_per_user_per_day:
            capped.append(user.user_id)
            continue
        eligible.append(user.user_id)
        queues[user.user_id] = bookings

    ordered: list[tuple[int, Booking]] = []
    while any(queues[uid] for uid in eligible):
        for uid in eligible:
            queue = queues[uid]
            if queue:
                ordered.append((uid, queue.pop(0)))

    return CheckPlan(ordered=ordered, capped_user_ids=capped)


def users_needing_capped_notice(
    capped_user_ids: Sequence[int], notice_sent_today: DailyCounter
) -> list[int]:
    """Which of `capped_user_ids` haven't been sent today's daily-limit notice
    yet (US-031: notify once per day, not every tick a user stays capped).

    Marks each returned user as notified as a side effect (increments their
    counter), so calling this twice in the same tick won't double-report.
    """
    due: list[int] = []
    for user_id in capped_user_ids:
        if notice_sent_today.count(user_id) == 0:
            due.append(user_id)
            notice_sent_today.increment(user_id)
    return due
