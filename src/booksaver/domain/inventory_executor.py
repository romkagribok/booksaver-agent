"""Provider-neutral contracts for positive-only account-inventory execution.

The executor is an untrusted perception/navigation capability.  Its observations may prove only
positive reservation facts; they never declare monitoring eligibility or authorize an absence
transition (ADR-039).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from .account_sync import ReservationLifecycle
from .browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionLimits,
    ExecutionUsage,
    ExecutorSafetyViolation,
    RedactedProvenance,
    RefundabilityEvidence,
    SessionLeaseReference,
)
from .value_objects import Money, Occupancy

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _safe_id(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not _SAFE_ID.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a bounded machine identifier")
    return normalized


def _bounded_optional_text(
    value: str | None,
    field_name: str,
    *,
    maximum: int = 500,
) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"{field_name} must contain 1-{maximum} normalized characters")
    return normalized


def _bounded_required_text(value: str, field_name: str, *, maximum: int = 500) -> str:
    normalized = _bounded_optional_text(value, field_name, maximum=maximum)
    assert normalized is not None
    return normalized


class InventoryScope(Enum):
    UPCOMING = "upcoming"
    PAST = "past"
    CANCELLED = "cancelled"


REQUIRED_INVENTORY_SCOPES = frozenset(InventoryScope)


class InventoryExecutionStatus(Enum):
    OBSERVED = "observed"
    SESSION_UNAVAILABLE = "session_unavailable"
    SIGNED_OUT = "signed_out"
    MFA_REQUIRED = "mfa_required"
    CAPTCHA = "captcha"
    BOT_WALL = "bot_wall"
    UNAVAILABLE = "unavailable"
    UNSAFE_ACTION = "unsafe_action"
    ACTION_LIMIT = "action_limit"
    COST_LIMIT = "cost_limit"
    TIMEOUT = "timeout"
    PROVIDER_FAILURE = "provider_failure"
    VALIDATION_FAILURE = "validation_failure"


def inventory_session_subject(owner_user_id: int) -> str:
    if isinstance(owner_user_id, bool) or owner_user_id < 1:
        raise ValueError("owner_user_id must be positive")
    return f"account:{owner_user_id}"


@dataclass(frozen=True, slots=True)
class ObservedInventoryScope:
    """Typed traversal evidence for one requested lifecycle scope.

    Even complete evidence is diagnostic only in this unit.  ADR-039 forbids using it to infer
    that an unseen persisted reservation is absent.
    """

    scope: InventoryScope
    requested_scope_visible: bool | None
    explicit_empty: bool | None
    pagination_exhausted: bool | None
    pages_observed: int
    visible_reservation_count: int
    detail_count: int
    completeness: EvidenceCompleteness

    def __post_init__(self) -> None:
        for field_name in (
            "requested_scope_visible",
            "explicit_empty",
            "pagination_exhausted",
        ):
            value = getattr(self, field_name)
            if value is not None and type(value) is not bool:
                raise TypeError(f"{field_name} must be boolean evidence or None")
        for field_name in ("pages_observed", "visible_reservation_count", "detail_count"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.pages_observed == 0 and any(
            value is not None
            for value in (
                self.requested_scope_visible,
                self.explicit_empty,
                self.pagination_exhausted,
            )
        ):
            raise ValueError("scope evidence cannot be visible without an observed page")
        if self.explicit_empty is True and self.visible_reservation_count != 0:
            raise ValueError("an explicit empty scope cannot contain visible reservations")


@dataclass(frozen=True, slots=True)
class ObservedReservation:
    """Positive visible reservation evidence returned by an untrusted executor."""

    remote_id: str = field(repr=False)
    identity_evidence: EvidenceCompleteness
    scope: InventoryScope
    lifecycle: ReservationLifecycle | None = None
    confirmation_id: str | None = field(default=None, repr=False)
    property_name: str | None = field(default=None, repr=False)
    property_reference: str | None = field(default=None, repr=False)
    check_in: date | None = None
    check_out: date | None = None
    room_type: str | None = field(default=None, repr=False)
    booked_total: Money | None = field(default=None, repr=False)
    all_in: AllInEvidence = AllInEvidence.UNKNOWN
    refundability: RefundabilityEvidence = RefundabilityEvidence.UNKNOWN
    refundability_text: str | None = field(default=None, repr=False)
    refund_deadline: date | None = None
    occupancy: Occupancy | None = None
    completeness: EvidenceCompleteness = EvidenceCompleteness.INCOMPLETE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "remote_id",
            _bounded_required_text(self.remote_id, "remote_id", maximum=500),
        )
        for field_name, maximum in (
            ("confirmation_id", 128),
            ("property_name", 500),
            ("property_reference", 500),
            ("room_type", 500),
            ("refundability_text", 1_000),
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_optional_text(
                    getattr(self, field_name),
                    field_name,
                    maximum=maximum,
                ),
            )
        if (self.check_in is None) != (self.check_out is None):
            raise ValueError("reservation stay dates must be both present or both absent")
        if self.check_in is not None and self.check_out is not None:
            if self.check_out <= self.check_in:
                raise ValueError("reservation check-out must be after check-in")
        if self.booked_total is not None and self.booked_total.amount <= 0:
            raise ValueError("observed booked total must be positive")
        if self.refund_deadline is not None and self.refundability is not (
            RefundabilityEvidence.EXPLICIT_REFUNDABLE
        ):
            raise ValueError("refund deadline requires explicit refundable evidence")


@dataclass(frozen=True, slots=True)
class InventoryExecutionRequest:
    execution_id: str
    owner_user_id: int
    session_lease: SessionLeaseReference
    limits: ExecutionLimits
    required_scopes: frozenset[InventoryScope] = REQUIRED_INVENTORY_SCOPES

    def __post_init__(self) -> None:
        _safe_id(self.execution_id, "execution_id")
        if isinstance(self.owner_user_id, bool) or self.owner_user_id < 1:
            raise ValueError("owner_user_id must be positive")
        if self.required_scopes != REQUIRED_INVENTORY_SCOPES:
            raise ValueError("inventory execution requires upcoming, past, and cancelled scopes")
        if (
            self.session_lease.owner_user_id != self.owner_user_id
            or self.session_lease.subject_id != inventory_session_subject(self.owner_user_id)
            or self.session_lease.execution_id != self.execution_id
        ):
            raise ValueError("session lease binding does not match the inventory request")


@dataclass(frozen=True, slots=True)
class InventoryExecutionResult:
    status: InventoryExecutionStatus
    authenticated: bool | None = None
    scopes: tuple[ObservedInventoryScope, ...] = ()
    reservations: tuple[ObservedReservation, ...] = ()
    provenance: RedactedProvenance | None = None
    refreshed_session_eligible: bool = False
    usage: ExecutionUsage = ExecutionUsage()
    latency_ms: int = 0
    fallback_used: bool = False
    safety_violations: frozenset[ExecutorSafetyViolation] = frozenset()

    def __post_init__(self) -> None:
        if isinstance(self.latency_ms, bool) or self.latency_ms < 0:
            raise ValueError("latency_ms must be a non-negative integer")
        if self.status is InventoryExecutionStatus.OBSERVED:
            if self.authenticated is not True or not self.scopes or self.provenance is None:
                raise ValueError(
                    "observed inventory requires authenticated scope evidence and provenance"
                )
        elif any(
            (
                self.authenticated is not None,
                bool(self.scopes),
                bool(self.reservations),
            )
        ):
            raise ValueError("non-observed inventory status cannot carry observation content")
        if (
            self.refreshed_session_eligible
            and self.status is not InventoryExecutionStatus.OBSERVED
        ):
            raise ValueError("only an observed execution can carry refresh eligibility")
        if self.safety_violations and self.status is not InventoryExecutionStatus.UNSAFE_ACTION:
            raise ValueError("safety violations require an unsafe-action terminal result")
