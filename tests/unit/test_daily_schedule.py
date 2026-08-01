from datetime import UTC, date, datetime, timedelta, timezone
from itertools import pairwise
from random import Random

import pytest

from booksaver.domain.schedule import (
    MissReason,
    ScheduledAdmission,
    ScheduledCheckSlot,
    ScheduleSettings,
    SlotIdentity,
    SlotStatus,
    generate_daily_slots,
)

SCHEDULE_DATE = date(2026, 8, 2)


def _identity(*, ordinal: int = 0) -> SlotIdentity:
    return SlotIdentity(user_id=7, schedule_date=SCHEDULE_DATE, ordinal=ordinal)


def test_schedule_settings_defaults_match_daily_policy() -> None:
    settings = ScheduleSettings()

    assert settings.checks_per_booking_per_day == 3
    assert settings.minimum_spacing == timedelta(hours=2)
    assert settings.missed_run_grace == timedelta(hours=1)
    assert settings.retention_days == 30


@pytest.mark.parametrize("count", [0, -1, True, 1.5])
def test_schedule_settings_require_a_positive_integer_count(count: object) -> None:
    with pytest.raises(ValueError, match="checks_per_booking_per_day"):
        ScheduleSettings(checks_per_booking_per_day=count)  # type: ignore[arg-type]


@pytest.mark.parametrize("spacing", [timedelta(0), timedelta(seconds=-1), "2h"])
def test_schedule_settings_require_positive_duration_spacing(spacing: object) -> None:
    with pytest.raises(ValueError, match="minimum_spacing"):
        ScheduleSettings(minimum_spacing=spacing)  # type: ignore[arg-type]


@pytest.mark.parametrize("grace", [timedelta(0), timedelta(seconds=-1), "1h"])
def test_schedule_settings_require_positive_duration_grace(grace: object) -> None:
    with pytest.raises(ValueError, match="missed_run_grace"):
        ScheduleSettings(missed_run_grace=grace)  # type: ignore[arg-type]


@pytest.mark.parametrize("retention_days", [0, -1, True, 2.5])
def test_schedule_settings_require_positive_integer_retention(retention_days: object) -> None:
    with pytest.raises(ValueError, match="retention_days"):
        ScheduleSettings(retention_days=retention_days)  # type: ignore[arg-type]


def test_schedule_settings_reject_spacing_that_leaves_no_random_range() -> None:
    with pytest.raises(ValueError, match="random range"):
        ScheduleSettings(
            checks_per_booking_per_day=3,
            minimum_spacing=timedelta(hours=8),
        )


def test_schedule_settings_accept_spacing_strictly_below_window_width() -> None:
    settings = ScheduleSettings(
        checks_per_booking_per_day=3,
        minimum_spacing=timedelta(hours=7, minutes=59, seconds=59),
    )

    assert settings.minimum_spacing < timedelta(hours=8)


def test_slot_identity_rejects_invalid_ordinal() -> None:
    with pytest.raises(ValueError, match="ordinal"):
        SlotIdentity(user_id=7, schedule_date=SCHEDULE_DATE, ordinal=-1)


def test_slot_identity_rejects_datetime_as_schedule_date() -> None:
    with pytest.raises(ValueError, match="schedule_date"):
        SlotIdentity(
            user_id=7,
            schedule_date=datetime(2026, 8, 2, tzinfo=UTC),  # type: ignore[arg-type]
            ordinal=0,
        )


def test_schedule_enums_expose_stable_persistence_values() -> None:
    assert {status.value for status in SlotStatus} == {
        "planned",
        "running",
        "completed",
        "missed",
    }
    assert {reason.value for reason in MissReason} == {
        "grace_expired",
        "superseded_catch_up",
        "spacing_conflict",
        "recovered_running",
        "user_unavailable",
        "stopping",
    }
    assert {admission.value for admission in ScheduledAdmission} == {
        "completed",
        "busy",
        "stopping",
        "stale",
    }


def test_planned_slot_exposes_identity_and_terminal_state() -> None:
    slot = ScheduledCheckSlot(
        identity=_identity(),
        planned_at=datetime(2026, 8, 2, 4, tzinfo=UTC),
    )

    assert slot.user_id == 7
    assert slot.schedule_date == SCHEDULE_DATE
    assert slot.ordinal == 0
    assert slot.status is SlotStatus.PLANNED
    assert not slot.is_terminal


def test_slot_requires_timezone_aware_utc_timestamps() -> None:
    with pytest.raises(ValueError, match="planned_at"):
        ScheduledCheckSlot(
            identity=_identity(),
            planned_at=datetime(2026, 8, 2, 4),
        )

    with pytest.raises(ValueError, match="planned_at"):
        ScheduledCheckSlot(
            identity=_identity(),
            planned_at=datetime(2026, 8, 2, 4, tzinfo=timezone(timedelta(hours=1))),
        )


def test_slot_planned_time_must_belong_to_identity_date() -> None:
    with pytest.raises(ValueError, match="schedule_date"):
        ScheduledCheckSlot(
            identity=_identity(),
            planned_at=datetime(2026, 8, 3, tzinfo=UTC),
        )


def test_slot_lifecycle_fields_match_status() -> None:
    planned_at = datetime(2026, 8, 2, 4, tzinfo=UTC)
    started_at = planned_at + timedelta(minutes=5)
    finished_at = started_at + timedelta(minutes=2)

    running = ScheduledCheckSlot(
        _identity(),
        planned_at,
        SlotStatus.RUNNING,
        started_at=started_at,
    )
    completed = ScheduledCheckSlot(
        _identity(),
        planned_at,
        SlotStatus.COMPLETED,
        started_at=started_at,
        finished_at=finished_at,
    )
    missed = ScheduledCheckSlot(
        _identity(),
        planned_at,
        SlotStatus.MISSED,
        finished_at=finished_at,
        miss_reason=MissReason.GRACE_EXPIRED,
    )

    assert not running.is_terminal
    assert completed.is_terminal
    assert missed.is_terminal


@pytest.mark.parametrize(
    ("status", "started_at", "finished_at", "miss_reason"),
    [
        (SlotStatus.PLANNED, datetime(2026, 8, 2, 4, 1, tzinfo=UTC), None, None),
        (SlotStatus.RUNNING, None, None, None),
        (
            SlotStatus.COMPLETED,
            datetime(2026, 8, 2, 4, 1, tzinfo=UTC),
            None,
            None,
        ),
        (SlotStatus.MISSED, None, datetime(2026, 8, 2, 4, 2, tzinfo=UTC), None),
    ],
)
def test_slot_rejects_inconsistent_lifecycle_fields(
    status: SlotStatus,
    started_at: datetime | None,
    finished_at: datetime | None,
    miss_reason: MissReason | None,
) -> None:
    with pytest.raises(ValueError):
        ScheduledCheckSlot(
            _identity(),
            datetime(2026, 8, 2, 4, tzinfo=UTC),
            status,
            started_at,
            finished_at,
            miss_reason,
        )


def test_slot_rejects_lifecycle_timestamps_before_planned_time() -> None:
    planned_at = datetime(2026, 8, 2, 4, tzinfo=UTC)

    with pytest.raises(ValueError, match="started_at"):
        ScheduledCheckSlot(
            _identity(),
            planned_at,
            SlotStatus.RUNNING,
            started_at=planned_at - timedelta(seconds=1),
        )


def test_default_generation_selects_one_slot_in_each_broad_window() -> None:
    slots = generate_daily_slots(
        7,
        SCHEDULE_DATE,
        ScheduleSettings(),
        randbelow=lambda _upper: 0,
    )

    assert [slot.planned_at for slot in slots] == [
        datetime(2026, 8, 2, 0, tzinfo=UTC),
        datetime(2026, 8, 2, 8, tzinfo=UTC),
        datetime(2026, 8, 2, 16, tzinfo=UTC),
    ]
    assert [slot.ordinal for slot in slots] == [0, 1, 2]
    assert all(slot.user_id == 7 for slot in slots)


def test_generation_constrains_later_draws_to_minimum_spacing() -> None:
    def choose_end_then_start(upper: int) -> int:
        return upper - 1 if choose_end_then_start.calls == 0 else 0

    choose_end_then_start.calls = 0  # type: ignore[attr-defined]

    def counted_choice(upper: int) -> int:
        result = choose_end_then_start(upper)
        choose_end_then_start.calls += 1  # type: ignore[attr-defined]
        return result

    slots = generate_daily_slots(
        7,
        SCHEDULE_DATE,
        ScheduleSettings(),
        randbelow=counted_choice,
    )

    assert slots[0].planned_at == datetime(2026, 8, 2, 7, 59, 59, tzinfo=UTC)
    assert slots[1].planned_at == datetime(2026, 8, 2, 9, 59, 59, tzinfo=UTC)
    assert slots[2].planned_at == datetime(2026, 8, 2, 16, tzinfo=UTC)
    assert all(
        later.planned_at - earlier.planned_at >= timedelta(hours=2)
        for earlier, later in pairwise(slots)
    )


def test_generation_applies_previous_day_boundary_to_first_window() -> None:
    prior = datetime(2026, 8, 1, 23, 30, tzinfo=UTC)

    slots = generate_daily_slots(
        7,
        SCHEDULE_DATE,
        ScheduleSettings(),
        randbelow=lambda _upper: 0,
        prior_day_final_planned_at=prior,
    )

    assert slots[0].planned_at == datetime(2026, 8, 2, 1, 30, tzinfo=UTC)
    assert slots[0].planned_at - prior == timedelta(hours=2)


def test_generation_rejects_invalid_previous_day_boundary() -> None:
    with pytest.raises(ValueError, match="prior_day_final_planned_at"):
        generate_daily_slots(
            7,
            SCHEDULE_DATE,
            ScheduleSettings(),
            randbelow=lambda _upper: 0,
            prior_day_final_planned_at=datetime(2026, 8, 1, 23, 30),
        )

    with pytest.raises(ValueError, match="precede"):
        generate_daily_slots(
            7,
            SCHEDULE_DATE,
            ScheduleSettings(),
            randbelow=lambda _upper: 0,
            prior_day_final_planned_at=datetime(2026, 8, 2, tzinfo=UTC),
        )


@pytest.mark.parametrize("bad_result", [-1, 28_800, True, 1.5])
def test_generation_rejects_random_source_contract_violations(bad_result: object) -> None:
    with pytest.raises(ValueError, match="randbelow"):
        generate_daily_slots(
            7,
            SCHEDULE_DATE,
            ScheduleSettings(),
            randbelow=lambda _upper: bad_result,  # type: ignore[return-value]
        )


def test_generation_supports_other_feasible_window_counts() -> None:
    slots = generate_daily_slots(
        9,
        SCHEDULE_DATE,
        ScheduleSettings(
            checks_per_booking_per_day=4,
            minimum_spacing=timedelta(hours=1),
        ),
        randbelow=lambda _upper: 0,
    )

    assert [slot.planned_at.hour for slot in slots] == [0, 6, 12, 18]


def test_many_seeded_schedules_stay_inside_windows_and_respect_spacing() -> None:
    settings = ScheduleSettings()
    day_start = datetime(2026, 8, 2, tzinfo=UTC)
    window_width = timedelta(hours=8)

    for seed in range(100):
        random = Random(seed)
        slots = generate_daily_slots(
            7,
            SCHEDULE_DATE,
            settings,
            randbelow=random.randrange,
            prior_day_final_planned_at=datetime(2026, 8, 1, 23, 59, 59, tzinfo=UTC),
        )

        previous = datetime(2026, 8, 1, 23, 59, 59, tzinfo=UTC)
        for ordinal, slot in enumerate(slots):
            assert day_start + ordinal * window_width <= slot.planned_at
            assert slot.planned_at < day_start + (ordinal + 1) * window_width
            assert slot.planned_at - previous >= settings.minimum_spacing
            previous = slot.planned_at
