from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from .value_objects import Money


class CheckOutcome(Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class ExtractionMethod(Enum):
    DOM = "dom"
    LLM = "llm"
    NONE = "none"


class FailureCode(Enum):
    NAVIGATION_ERROR = "navigation_error"
    AUTH_REQUIRED = "auth_required"
    EXTRACTION_FAILED = "extraction_failed"
    LLM_ERROR = "llm_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FailureReason:
    code: FailureCode
    detail: str


@dataclass(frozen=True)
class RefundIndicators:
    is_refundable: bool | None
    cancellation_deadline: date | None = None
    raw_text: str | None = None


@dataclass(frozen=True)
class ExtractedBookingFields:
    property_name: str | None = None
    room_label: str | None = None
    check_in: date | None = None
    check_out: date | None = None


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    booking_id: str
    checked_at: datetime
    outcome: CheckOutcome
    extraction_method: ExtractionMethod
    live_price: Money | None = None
    refund_indicators: RefundIndicators | None = None
    extracted_fields: ExtractedBookingFields | None = None
    failure_reason: FailureReason | None = None

    def __post_init__(self) -> None:
        if self.outcome is CheckOutcome.SUCCESS and self.live_price is None:
            raise ValueError("A successful check must have a live_price")
        if self.outcome is CheckOutcome.FAILURE and self.failure_reason is None:
            raise ValueError("A failed check must have a failure_reason")

    @classmethod
    def success(
        cls,
        booking_id: str,
        checked_at: datetime,
        live_price: Money,
        extraction_method: ExtractionMethod,
        refund_indicators: RefundIndicators | None = None,
        extracted_fields: ExtractedBookingFields | None = None,
    ) -> CheckResult:
        return cls(
            check_id=str(uuid.uuid4()),
            booking_id=booking_id,
            checked_at=checked_at,
            outcome=CheckOutcome.SUCCESS,
            extraction_method=extraction_method,
            live_price=live_price,
            refund_indicators=refund_indicators,
            extracted_fields=extracted_fields,
        )

    @classmethod
    def failure(
        cls,
        booking_id: str,
        checked_at: datetime,
        reason: FailureReason,
    ) -> CheckResult:
        return cls(
            check_id=str(uuid.uuid4()),
            booking_id=booking_id,
            checked_at=checked_at,
            outcome=CheckOutcome.FAILURE,
            extraction_method=ExtractionMethod.NONE,
            failure_reason=reason,
        )
