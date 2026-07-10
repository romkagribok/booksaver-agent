from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from .check_result import CheckOutcome, CheckResult
from .models import Booking
from .value_objects import Money


class RejectionReason(Enum):
    DATES_DIFFER = "dates_differ"
    PROPERTY_DIFFERS = "property_differs"
    ROOM_DIFFERS = "room_differs"
    NOT_REFUNDABLE = "not_refundable"
    REFUNDABILITY_UNKNOWN = "refundability_unknown"
    CURRENCY_MISMATCH = "currency_mismatch"
    PRICE_NOT_LOWER = "price_not_lower"


@dataclass(frozen=True)
class EquivalenceVerdict:
    equivalent: bool
    rejection_reason: RejectionReason | None = None


@dataclass(frozen=True)
class SavingsOpportunity:
    opportunity_id: str
    booking_id: str
    check_id: str
    baseline_price: Money
    live_price: Money
    amount_saved: Money
    percent_saved: Decimal
    validated_at: datetime
    notified_at: datetime | None = None

    def with_notified_at(self, at: datetime) -> SavingsOpportunity:
        return replace(self, notified_at=at)


def evaluate_equivalence(booking: Booking, result: CheckResult) -> EquivalenceVerdict:
    """The US-008 gate.

    Dates/property/room: a value extracted from the page that CONTRADICTS the booking
    rejects the offer; an absent value passes (the monitored page is the reservation's
    own manage page, so absence is non-contradiction). Refundability is the exception:
    it must be positively confirmed — absent or false both reject.
    """
    fields = result.extracted_fields
    if fields is not None:
        if fields.check_in is not None and fields.check_in != booking.stay_dates.check_in:
            return EquivalenceVerdict(False, RejectionReason.DATES_DIFFER)
        if fields.check_out is not None and fields.check_out != booking.stay_dates.check_out:
            return EquivalenceVerdict(False, RejectionReason.DATES_DIFFER)
        if (
            fields.property_name is not None
            and fields.property_name.strip().lower() != booking.property.name.strip().lower()
        ):
            return EquivalenceVerdict(False, RejectionReason.PROPERTY_DIFFERS)
        if (
            fields.room_label is not None
            and fields.room_label.strip().lower() != booking.room_type.label.strip().lower()
        ):
            return EquivalenceVerdict(False, RejectionReason.ROOM_DIFFERS)

    indicators = result.refund_indicators
    if indicators is None or indicators.is_refundable is None:
        return EquivalenceVerdict(False, RejectionReason.REFUNDABILITY_UNKNOWN)
    if indicators.is_refundable is False:
        return EquivalenceVerdict(False, RejectionReason.NOT_REFUNDABLE)

    return EquivalenceVerdict(True)


def detect_savings(
    booking: Booking, result: CheckResult
) -> SavingsOpportunity | RejectionReason:
    """US-007 + US-008: gate first, then strict same-currency price comparison."""
    if result.outcome is not CheckOutcome.SUCCESS or result.live_price is None:
        raise ValueError("detect_savings requires a successful check with a live price")

    verdict = evaluate_equivalence(booking, result)
    if not verdict.equivalent:
        assert verdict.rejection_reason is not None
        return verdict.rejection_reason

    live = result.live_price
    baseline = booking.baseline_price

    if live.currency != baseline.currency:
        return RejectionReason.CURRENCY_MISMATCH
    if live.amount >= baseline.amount:
        return RejectionReason.PRICE_NOT_LOWER

    saved = baseline.amount - live.amount
    percent = (saved / baseline.amount * 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return SavingsOpportunity(
        opportunity_id=str(uuid.uuid4()),
        booking_id=booking.booking_id,
        check_id=result.check_id,
        baseline_price=baseline,
        live_price=live,
        amount_saved=Money(amount=saved, currency=baseline.currency),
        percent_saved=percent,
        validated_at=result.checked_at,
    )
