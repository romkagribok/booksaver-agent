"""When a monitored reservation has stopped getting conclusive price results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from booksaver.domain.account_sync import EligibilityReason, EligibilityStatus

STALL_AFTER = timedelta(hours=24)

# Reasons a change or an unreadable page can cause; every other reason is ineligible by design.
_HOLD_REASONS = frozenset({
    EligibilityReason.MISSING_BOOKED_TOTAL,
    EligibilityReason.MISSING_ROOM_TYPE,
    EligibilityReason.MISSING_OCCUPANCY,
    EligibilityReason.REFUNDABILITY_UNKNOWN,
})


class StallReason(Enum):
    SYNC_FAILING = "sync_failing"
    TOTAL_UNCONFIRMED = "total_unconfirmed"
    CHECKS_FAILING = "checks_failing"


@dataclass(frozen=True, slots=True)
class MonitoredReservation:
    booking_id: str
    property_name: str
    eligibility: EligibilityStatus
    eligibility_reasons: frozenset[EligibilityReason]
    first_observed_at: datetime
    last_conclusive_at: datetime | None
    latest_sync_failed: bool


def is_monitored(reservation: MonitoredReservation) -> bool:
    """Eligible, or held on a fact that a later sync can still establish."""
    return reservation.eligibility is EligibilityStatus.ELIGIBLE or (
        reservation.eligibility_reasons <= _HOLD_REASONS and bool(reservation.eligibility_reasons)
    )


def stall_reason(reservation: MonitoredReservation, now: datetime) -> StallReason | None:
    """Why this reservation has stalled at ``now``, or None when it has not."""
    if not is_monitored(reservation):
        return None
    since = max(
        reservation.first_observed_at,
        reservation.last_conclusive_at or reservation.first_observed_at,
    )
    if now - since < STALL_AFTER:
        return None
    if reservation.latest_sync_failed:
        return StallReason.SYNC_FAILING
    if reservation.eligibility is not EligibilityStatus.ELIGIBLE:
        return StallReason.TOTAL_UNCONFIRMED
    return StallReason.CHECKS_FAILING


def stall_message(reservation: MonitoredReservation, reason: StallReason) -> tuple[str, str]:
    name = reservation.property_name
    cause = {
        StallReason.SYNC_FAILING: "BookSaver can't read this reservation from your account.",
        StallReason.TOTAL_UNCONFIRMED: (
            "BookSaver can't confirm your booked total or terms since the reservation changed, "
            "so it won't report savings."
        ),
        StallReason.CHECKS_FAILING: "Its price checks keep failing.",
    }[reason]
    return (
        f"BookSaver: {name} isn't being checked",
        f"{name} has had no verified price for over 24 hours. {cause} You may want to check "
        "Booking.com yourself. BookSaver keeps trying and will tell you when this recovers.",
    )


def recovery_message(reservation: MonitoredReservation) -> tuple[str, str]:
    name = reservation.property_name
    return (
        f"BookSaver: {name} is being checked again",
        f"Price checks for {name} are working again.",
    )
