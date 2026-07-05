from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from booksaver.domain.check_result import (
    CheckResult,
    ExtractedBookingFields,
    ExtractionMethod,
    FailureCode,
    FailureReason,
    RefundIndicators,
)
from booksaver.domain.savings import (
    RejectionReason,
    SavingsOpportunity,
    detect_savings,
    evaluate_equivalence,
)
from booksaver.domain.value_objects import Money

from ..monitor.fakes import make_booking

# The registered booking: Hotel Test, Standard Double, 2026-09-01 -> 09-05, 400.00 EUR


def _check(
    amount: str = "350.00",
    currency: str = "EUR",
    refundable: bool | None = True,
    fields: ExtractedBookingFields | None = None,
) -> CheckResult:
    return CheckResult.success(
        booking_id="b-1",
        checked_at=datetime.now(UTC),
        live_price=Money(amount=Decimal(amount), currency=currency),
        extraction_method=ExtractionMethod.DOM,
        refund_indicators=RefundIndicators(is_refundable=refundable),
        extracted_fields=fields,
    )


# ── equivalence gate (US-008) ─────────────────────────────────────────────────

def test_equivalent_when_refundable_and_no_contradictions() -> None:
    verdict = evaluate_equivalence(make_booking(), _check())
    assert verdict.equivalent is True
    assert verdict.rejection_reason is None


def test_matching_extracted_fields_pass() -> None:
    fields = ExtractedBookingFields(
        property_name="Hotel Test",
        room_label="Standard Double",
        check_in=date(2026, 9, 1),
        check_out=date(2026, 9, 5),
    )
    verdict = evaluate_equivalence(make_booking(), _check(fields=fields))
    assert verdict.equivalent is True


def test_case_insensitive_property_and_room_match() -> None:
    fields = ExtractedBookingFields(property_name="HOTEL TEST", room_label="standard double")
    verdict = evaluate_equivalence(make_booking(), _check(fields=fields))
    assert verdict.equivalent is True


def test_different_check_in_rejected() -> None:
    fields = ExtractedBookingFields(check_in=date(2026, 9, 2))
    verdict = evaluate_equivalence(make_booking(), _check(fields=fields))
    assert verdict.rejection_reason is RejectionReason.DATES_DIFFER


def test_different_check_out_rejected() -> None:
    fields = ExtractedBookingFields(check_out=date(2026, 9, 6))
    verdict = evaluate_equivalence(make_booking(), _check(fields=fields))
    assert verdict.rejection_reason is RejectionReason.DATES_DIFFER


def test_different_property_rejected() -> None:
    fields = ExtractedBookingFields(property_name="Another Hotel")
    verdict = evaluate_equivalence(make_booking(), _check(fields=fields))
    assert verdict.rejection_reason is RejectionReason.PROPERTY_DIFFERS


def test_different_room_rejected() -> None:
    fields = ExtractedBookingFields(room_label="Suite")
    verdict = evaluate_equivalence(make_booking(), _check(fields=fields))
    assert verdict.rejection_reason is RejectionReason.ROOM_DIFFERS


def test_not_refundable_rejected_even_if_fields_match() -> None:
    verdict = evaluate_equivalence(make_booking(), _check(refundable=False))
    assert verdict.rejection_reason is RejectionReason.NOT_REFUNDABLE


def test_unknown_refundability_rejected() -> None:
    # US-008: refundability must be positively confirmed; absence rejects
    verdict = evaluate_equivalence(make_booking(), _check(refundable=None))
    assert verdict.rejection_reason is RejectionReason.REFUNDABILITY_UNKNOWN


def test_missing_refund_indicators_rejected() -> None:
    result = CheckResult.success(
        booking_id="b-1",
        checked_at=datetime.now(UTC),
        live_price=Money(amount=Decimal("100"), currency="EUR"),
        extraction_method=ExtractionMethod.DOM,
        refund_indicators=None,
    )
    verdict = evaluate_equivalence(make_booking(), result)
    assert verdict.rejection_reason is RejectionReason.REFUNDABILITY_UNKNOWN


# ── price comparison (US-007) ─────────────────────────────────────────────────

def test_cheaper_equivalent_refundable_offer_detected() -> None:
    detection = detect_savings(make_booking(), _check(amount="350.00"))
    assert isinstance(detection, SavingsOpportunity)
    assert detection.amount_saved == Money(amount=Decimal("50.00"), currency="EUR")
    assert detection.percent_saved == Decimal("12.50")


def test_equal_price_rejected() -> None:
    detection = detect_savings(make_booking(), _check(amount="400.00"))
    assert detection is RejectionReason.PRICE_NOT_LOWER


def test_higher_price_rejected() -> None:
    detection = detect_savings(make_booking(), _check(amount="450.00"))
    assert detection is RejectionReason.PRICE_NOT_LOWER


def test_one_cent_cheaper_is_detected() -> None:
    detection = detect_savings(make_booking(), _check(amount="399.99"))
    assert isinstance(detection, SavingsOpportunity)
    assert detection.amount_saved.amount == Decimal("0.01")


def test_currency_mismatch_rejected() -> None:
    assert (
        detect_savings(make_booking(), _check(amount="100.00", currency="USD"))
        is RejectionReason.CURRENCY_MISMATCH
    )


def test_gate_rejection_takes_priority_over_price() -> None:
    # Cheaper but not refundable — must be rejected by the gate
    detection = detect_savings(make_booking(), _check(amount="100.00", refundable=False))
    assert detection is RejectionReason.NOT_REFUNDABLE


def test_failed_check_raises() -> None:
    failed = CheckResult.failure(
        "b-1",
        datetime.now(UTC),
        FailureReason(code=FailureCode.TIMEOUT, detail="x"),
    )
    with pytest.raises(ValueError, match="successful check"):
        detect_savings(make_booking(), failed)


def test_percent_rounding_two_decimals() -> None:
    # 400 -> 266.67 saves 133.33 = 33.3325% -> 33.33
    detection = detect_savings(make_booking(), _check(amount="266.67"))
    assert isinstance(detection, SavingsOpportunity)
    assert detection.percent_saved == Decimal("33.33")
