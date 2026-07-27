from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum

from .value_objects import Money, Occupancy


class InventoryCompleteness(Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class ReservationLifecycle(Enum):
    UPCOMING = "upcoming"
    CURRENT = "current"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"
    ABSENT = "absent"


class EligibilityStatus(Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class EligibilityReason(Enum):
    PAST_OR_COMPLETED = "past_or_completed"
    CANCELLED = "cancelled"
    NOT_UPCOMING = "not_upcoming"
    NON_REFUNDABLE = "non_refundable"
    REFUNDABILITY_UNKNOWN = "refundability_unknown"
    MISSING_CONFIRMATION = "missing_confirmation"
    MISSING_PROPERTY = "missing_property"
    MISSING_STAY_DATES = "missing_stay_dates"
    MISSING_ROOM_TYPE = "missing_room_type"
    MISSING_OCCUPANCY = "missing_occupancy"
    MISSING_BOOKED_TOTAL = "missing_booked_total"
    NOT_OBSERVED = "not_observed"


class SynchronizationTrigger(Enum):
    CONNECT = "connect"
    SESSION_INTAKE = "session_intake"
    SCHEDULED = "scheduled"
    CHECK_NOW = "check_now"
    BOOKINGS = "bookings"


class SynchronizationFailureCode(Enum):
    AUTH_REQUIRED = "auth_required"
    NAVIGATION_FAILED = "navigation_failed"
    UNSUPPORTED_LAYOUT = "unsupported_layout"
    PAGINATION_INCOMPLETE = "pagination_incomplete"
    IDENTITY_AMBIGUOUS = "identity_ambiguous"
    EXTRACTION_AMBIGUOUS = "extraction_ambiguous"
    PERSISTENCE_CONFLICT = "persistence_conflict"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ReservationObservation:
    remote_id: str
    lifecycle: ReservationLifecycle
    observed_at: datetime
    confirmation_id: str | None = None
    property_name: str | None = None
    property_ref: str | None = None
    check_in: date | None = None
    check_out: date | None = None
    room_type: str | None = None
    booked_total: Money | None = None
    refundable: bool | None = None
    refund_note: str = ""
    refund_deadline: date | None = None
    occupancy: Occupancy | None = None
    source_url: str = ""
    extraction_method: str = "dom"

    def __post_init__(self) -> None:
        if not self.remote_id.strip():
            raise ValueError("Remote reservation identity must be non-empty")
        if self.check_in is not None and self.check_out is not None:
            if self.check_out <= self.check_in:
                raise ValueError("Reservation check-out must be after check-in")


@dataclass(frozen=True, slots=True)
class InventoryDiscoveryResult:
    observations: tuple[ReservationObservation, ...]
    completeness: InventoryCompleteness
    failure_code: SynchronizationFailureCode | None = None
    failure_detail: str | None = None

    def __post_init__(self) -> None:
        if self.completeness is InventoryCompleteness.FAILED and self.failure_code is None:
            raise ValueError("Failed inventory discovery requires a failure code")
        if self.completeness is InventoryCompleteness.COMPLETE and self.failure_code is not None:
            raise ValueError("Complete discovery cannot carry a failure code")

    @classmethod
    def failed(
        cls, code: SynchronizationFailureCode, detail: str
    ) -> InventoryDiscoveryResult:
        return cls((), InventoryCompleteness.FAILED, code, detail)


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    status: EligibilityStatus
    reasons: tuple[EligibilityReason, ...]

    @property
    def is_eligible(self) -> bool:
        return self.status is EligibilityStatus.ELIGIBLE


@dataclass(frozen=True, slots=True)
class AccountReservation:
    account_reservation_id: str
    user_id: int
    remote_key_hash: str
    observation: ReservationObservation
    eligibility: EligibilityDecision
    monitoring_booking_id: str | None
    first_observed_at: datetime
    last_observed_at: datetime
    snapshot_revision: int


@dataclass(frozen=True, slots=True)
class SynchronizationReport:
    run_id: str
    completeness: InventoryCompleteness
    discovered: int
    eligible: int
    ineligible: int
    failure_code: SynchronizationFailureCode | None = None
    failure_detail: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.completeness is InventoryCompleteness.COMPLETE


def remote_key_hash(user_id: int, remote_id: str) -> str:
    material = f"{user_id}\0{remote_id.strip()}".encode()
    return hashlib.sha256(material).hexdigest()


def evaluate_eligibility(
    observation: ReservationObservation, *, today: date | None = None
) -> EligibilityDecision:
    current_date = today or datetime.now(UTC).date()
    reasons: list[EligibilityReason] = []

    if observation.lifecycle is ReservationLifecycle.ABSENT:
        reasons.append(EligibilityReason.NOT_OBSERVED)
    elif observation.lifecycle is ReservationLifecycle.CANCELLED:
        reasons.append(EligibilityReason.CANCELLED)
    elif observation.lifecycle is ReservationLifecycle.COMPLETED:
        reasons.append(EligibilityReason.PAST_OR_COMPLETED)
    elif observation.lifecycle is not ReservationLifecycle.UPCOMING:
        reasons.append(EligibilityReason.NOT_UPCOMING)

    if observation.check_out is not None and observation.check_out <= current_date:
        _append_once(reasons, EligibilityReason.PAST_OR_COMPLETED)
    if observation.refundable is False:
        reasons.append(EligibilityReason.NON_REFUNDABLE)
    elif observation.refundable is None:
        reasons.append(EligibilityReason.REFUNDABILITY_UNKNOWN)
    if not observation.confirmation_id:
        reasons.append(EligibilityReason.MISSING_CONFIRMATION)
    if not observation.property_name or not observation.property_ref:
        reasons.append(EligibilityReason.MISSING_PROPERTY)
    if observation.check_in is None or observation.check_out is None:
        reasons.append(EligibilityReason.MISSING_STAY_DATES)
    if not observation.room_type:
        reasons.append(EligibilityReason.MISSING_ROOM_TYPE)
    if observation.occupancy is None:
        reasons.append(EligibilityReason.MISSING_OCCUPANCY)
    if observation.booked_total is None:
        reasons.append(EligibilityReason.MISSING_BOOKED_TOTAL)

    return EligibilityDecision(
        EligibilityStatus.ELIGIBLE if not reasons else EligibilityStatus.INELIGIBLE,
        tuple(reasons),
    )


def _append_once(
    reasons: list[EligibilityReason], reason: EligibilityReason
) -> None:
    if reason not in reasons:
        reasons.append(reason)
