from __future__ import annotations

from datetime import UTC, datetime

from booksaver.domain.user import User, UserAccessState, UserRole
from booksaver.monitor.user_limits import (
    DailyCounter,
    build_check_plan,
    users_needing_capped_notice,
)

from .fakes import make_booking


def _user(user_id: int) -> User:
    return User(
        user_id=user_id,
        telegram_user_id=user_id,
        role=UserRole.USER,
        access_state=UserAccessState.ACTIVE,
        created_at=datetime.now(UTC),
    )


# ── DailyCounter ─────────────────────────────────────────────────────────────


def test_daily_counter_increments_and_reads_back() -> None:
    counter = DailyCounter(clock=lambda: datetime(2026, 7, 11, tzinfo=UTC))
    assert counter.count(1) == 0
    counter.increment(1)
    counter.increment(1)
    assert counter.count(1) == 2


def test_daily_counter_keys_are_independent() -> None:
    counter = DailyCounter(clock=lambda: datetime(2026, 7, 11, tzinfo=UTC))
    counter.increment(1)
    counter.increment(2, by=5)
    assert counter.count(1) == 1
    assert counter.count(2) == 5


def test_daily_counter_rolls_over_at_utc_midnight() -> None:
    current = {"now": datetime(2026, 7, 11, 23, 59, tzinfo=UTC)}
    counter = DailyCounter(clock=lambda: current["now"])
    counter.increment(1, by=10)
    assert counter.count(1) == 10

    current["now"] = datetime(2026, 7, 12, 0, 1, tzinfo=UTC)
    assert counter.count(1) == 0
    counter.increment(1)
    assert counter.count(1) == 1


def test_daily_counter_snapshot_reflects_current_day() -> None:
    counter = DailyCounter(clock=lambda: datetime(2026, 7, 11, tzinfo=UTC))
    counter.increment(1)
    counter.increment(2)
    assert counter.snapshot() == {1: 1, 2: 1}


# ── build_check_plan ─────────────────────────────────────────────────────────


def test_bookings_are_interleaved_round_robin_across_users() -> None:
    user_a, user_b = _user(1), _user(2)
    a1, a2 = make_booking("a-1"), make_booking("a-2")
    b1 = make_booking("b-1")

    plan = build_check_plan(
        users=[user_a, user_b],
        bookings_by_user={1: [a1, a2], 2: [b1]},
        checks_today={},
        max_checks_per_user_per_day=48,
    )

    ordered_ids = [(uid, b.booking_id) for uid, b in plan.ordered]
    # a1 and b1 interleave before a2 (b never starves behind a's second booking)
    assert ordered_ids == [(1, "a-1"), (2, "b-1"), (1, "a-2")]
    assert plan.capped_user_ids == []


def test_user_at_daily_cap_is_excluded_and_reported() -> None:
    user_a, user_b = _user(1), _user(2)
    plan = build_check_plan(
        users=[user_a, user_b],
        bookings_by_user={1: [make_booking("a-1")], 2: [make_booking("b-1")]},
        checks_today={1: 48},
        max_checks_per_user_per_day=48,
    )

    assert [uid for uid, _b in plan.ordered] == [2]
    assert plan.capped_user_ids == [1]


def test_users_with_no_bookings_are_skipped_silently() -> None:
    user_a = _user(1)
    plan = build_check_plan(
        users=[user_a],
        bookings_by_user={},
        checks_today={},
        max_checks_per_user_per_day=48,
    )
    assert plan.ordered == []
    assert plan.capped_user_ids == []


def test_empty_users_produces_empty_plan() -> None:
    plan = build_check_plan(
        users=[], bookings_by_user={}, checks_today={}, max_checks_per_user_per_day=48
    )
    assert plan.ordered == []
    assert plan.capped_user_ids == []


# ── users_needing_capped_notice ─────────────────────────────────────────────


def test_first_tick_capped_reports_the_user_as_due() -> None:
    notice_sent = DailyCounter(clock=lambda: datetime(2026, 7, 11, tzinfo=UTC))
    due = users_needing_capped_notice([1, 2], notice_sent)
    assert due == [1, 2]


def test_repeat_ticks_same_day_do_not_re_notify() -> None:
    notice_sent = DailyCounter(clock=lambda: datetime(2026, 7, 11, tzinfo=UTC))
    first = users_needing_capped_notice([1], notice_sent)
    second = users_needing_capped_notice([1], notice_sent)
    assert first == [1]
    assert second == []


def test_next_day_notifies_again() -> None:
    current = {"now": datetime(2026, 7, 11, 23, 0, tzinfo=UTC)}
    notice_sent = DailyCounter(clock=lambda: current["now"])
    assert users_needing_capped_notice([1], notice_sent) == [1]
    assert users_needing_capped_notice([1], notice_sent) == []

    current["now"] = datetime(2026, 7, 12, 1, 0, tzinfo=UTC)
    assert users_needing_capped_notice([1], notice_sent) == [1]


def test_no_capped_users_produces_no_notices() -> None:
    notice_sent = DailyCounter(clock=lambda: datetime(2026, 7, 11, tzinfo=UTC))
    assert users_needing_capped_notice([], notice_sent) == []
