from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from booksaver.domain.account_sync import EligibilityReason, EligibilityStatus
from booksaver.domain.monitoring_stall import (
    MonitoredReservation,
    StallReason,
    stall_message,
    stall_reason,
)

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)


def _reservation(**facts: object) -> MonitoredReservation:
    values: dict[str, object] = {
        "booking_id": "booking-1",
        "property_name": "Synthetic Hotel",
        "eligibility": EligibilityStatus.ELIGIBLE,
        "eligibility_reasons": frozenset(),
        "first_observed_at": NOW - timedelta(days=30),
        "last_conclusive_at": NOW - timedelta(hours=25),
        "latest_sync_failed": False,
    }
    return MonitoredReservation(**{**values, **facts})  # type: ignore[arg-type]


def test_stalls_only_after_24_hours_without_a_conclusive_result() -> None:
    assert stall_reason(_reservation(last_conclusive_at=NOW - timedelta(hours=23)), NOW) is None
    assert stall_reason(
        _reservation(last_conclusive_at=NOW - timedelta(hours=24)), NOW,
    ) is StallReason.CHECKS_FAILING


def test_a_new_reservation_gets_a_day_before_it_can_stall() -> None:
    assert stall_reason(
        _reservation(first_observed_at=NOW - timedelta(hours=2), last_conclusive_at=None), NOW,
    ) is None


def test_sync_failure_takes_precedence_then_a_hold() -> None:
    hold = {
        "eligibility": EligibilityStatus.INELIGIBLE,
        "eligibility_reasons": frozenset({EligibilityReason.MISSING_BOOKED_TOTAL}),
    }
    assert stall_reason(_reservation(**hold), NOW) is StallReason.TOTAL_UNCONFIRMED
    assert stall_reason(
        _reservation(**hold, latest_sync_failed=True), NOW,
    ) is StallReason.SYNC_FAILING


@pytest.mark.parametrize(
    "reasons",
    [
        {EligibilityReason.NON_REFUNDABLE},
        {EligibilityReason.NON_REFUNDABLE, EligibilityReason.MISSING_BOOKED_TOTAL},
        {EligibilityReason.CANCELLED},
        set(),
    ],
)
def test_a_reservation_ineligible_by_design_never_stalls(
    reasons: set[EligibilityReason],
) -> None:
    assert stall_reason(_reservation(
        eligibility=EligibilityStatus.INELIGIBLE, eligibility_reasons=frozenset(reasons),
    ), NOW) is None


@pytest.mark.parametrize("reason", list(StallReason))
def test_each_message_names_the_hotel_and_a_plain_cause(reason: StallReason) -> None:
    subject, body = stall_message(_reservation(), reason)
    assert "Synthetic Hotel" in subject
    assert "24 hours" in body
