"""Application services for positive-only agentic account inventory (ADR-039)."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TypeVar

from booksaver.application.browser_executor import InMemorySessionLeaseBroker
from booksaver.application.ports import InventoryBrowserExecutor
from booksaver.domain.account_sync import (
    InventoryCompleteness,
    InventoryDiscoveryResult,
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationFailureCode,
)
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionLimits,
    RefundabilityEvidence,
)
from booksaver.domain.inventory_executor import (
    REQUIRED_INVENTORY_SCOPES,
    InventoryExecutionRequest,
    InventoryExecutionResult,
    InventoryExecutionStatus,
    InventoryScope,
    ObservedInventoryScope,
    ObservedReservation,
    inventory_session_subject,
)


class InventoryValidationFailure(Enum):
    EXECUTION_NOT_OBSERVED = "execution_not_observed"
    EXECUTION_LIMIT_BREACH = "execution_limit_breach"
    AUTHENTICATION_REQUIRED = "authentication_required"
    IDENTITY_AMBIGUOUS = "identity_ambiguous"
    NO_VALID_POSITIVE_OBSERVATION = "no_valid_positive_observation"


@dataclass(frozen=True, slots=True)
class InventoryObservationValidation:
    observations: tuple[ReservationObservation, ...] = ()
    rejected_reservation_count: int = 0
    traversal_claim_complete: bool = False
    scope_count: int = 0
    page_count: int = 0
    detail_count: int = 0
    failure: InventoryValidationFailure | None = None
    failure_code: SynchronizationFailureCode | None = None
    failure_detail: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "rejected_reservation_count",
            "scope_count",
            "page_count",
            "detail_count",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if (self.failure is None) != (self.failure_code is None):
            raise ValueError("validation failure and synchronization failure code must agree")
        if self.failure is not None and self.observations:
            raise ValueError("failed validation cannot carry accepted observations")

    @property
    def accepted_positive_count(self) -> int:
        return len(self.observations)

    def to_discovery_result(self) -> InventoryDiscoveryResult:
        if self.failure is not None:
            assert self.failure_code is not None
            return InventoryDiscoveryResult.failed(
                self.failure_code,
                self.failure_detail or "Agentic inventory validation failed closed.",
            )
        # ADR-039 is deliberately stronger than a model's account-completeness claim.  Returning
        # INCOMPLETE lets the existing repository upsert positives while preserving every unseen
        # reservation.
        return InventoryDiscoveryResult(
            observations=self.observations,
            completeness=InventoryCompleteness.INCOMPLETE,
            failure_code=(
                SynchronizationFailureCode.EXTRACTION_AMBIGUOUS
                if self.rejected_reservation_count
                else None
            ),
            failure_detail=(
                "Some visible reservations lacked complete stable positive evidence; "
                "all unseen saved reservations were preserved."
                if self.rejected_reservation_count
                else (
                    "Agentic inventory accepted current positive observations; unseen saved "
                    "reservations were preserved by policy."
                )
            ),
        )


class InventoryObservationValidator:
    """Map untrusted typed evidence to positive-only BookSaver reservation facts."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def validate(
        self,
        request: InventoryExecutionRequest,
        result: InventoryExecutionResult,
    ) -> InventoryObservationValidation:
        scopes = result.scopes
        scope_count = len(scopes)
        page_count = sum(scope.pages_observed for scope in scopes)
        detail_count = sum(scope.detail_count for scope in scopes)
        observed_at = self._clock()
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("inventory validation clock must be timezone-aware")
        if (
            not result.usage.within(request.limits)
            or observed_at >= request.limits.deadline
            or result.latency_ms > request.limits.timeout_seconds * 1_000
        ):
            return self._failure(
                InventoryValidationFailure.EXECUTION_LIMIT_BREACH,
                SynchronizationFailureCode.NAVIGATION_FAILED,
                "Agentic inventory exceeded an execution limit; last-safe state was preserved.",
                scope_count=scope_count,
                page_count=page_count,
                detail_count=detail_count,
            )
        if result.status is not InventoryExecutionStatus.OBSERVED:
            code, detail = _terminal_failure(result.status)
            return self._failure(
                InventoryValidationFailure.EXECUTION_NOT_OBSERVED,
                code,
                detail,
                scope_count=scope_count,
                page_count=page_count,
                detail_count=detail_count,
            )
        if result.authenticated is not True:
            return self._failure(
                InventoryValidationFailure.AUTHENTICATION_REQUIRED,
                SynchronizationFailureCode.AUTH_REQUIRED,
                "Booking.com account authentication is required.",
                scope_count=scope_count,
                page_count=page_count,
                detail_count=detail_count,
            )

        merged, rejected, conflict = _validated_unique_reservations(result.reservations)
        if conflict:
            return self._failure(
                InventoryValidationFailure.IDENTITY_AMBIGUOUS,
                SynchronizationFailureCode.IDENTITY_AMBIGUOUS,
                "Booking.com returned conflicting positive reservation identities.",
                rejected_reservation_count=max(1, rejected),
                scope_count=scope_count,
                page_count=page_count,
                detail_count=detail_count,
            )
        observations = tuple(_to_reservation_observation(item, observed_at) for item in merged)
        return InventoryObservationValidation(
            observations=observations,
            rejected_reservation_count=rejected,
            traversal_claim_complete=_traversal_claim_complete(scopes, result.reservations),
            scope_count=scope_count,
            page_count=page_count,
            detail_count=detail_count,
        )

    @staticmethod
    def _failure(
        failure: InventoryValidationFailure,
        code: SynchronizationFailureCode,
        detail: str,
        *,
        rejected_reservation_count: int = 0,
        scope_count: int = 0,
        page_count: int = 0,
        detail_count: int = 0,
    ) -> InventoryObservationValidation:
        return InventoryObservationValidation(
            rejected_reservation_count=rejected_reservation_count,
            scope_count=scope_count,
            page_count=page_count,
            detail_count=detail_count,
            failure=failure,
            failure_code=code,
            failure_detail=detail,
        )


class FakeInventoryBrowserExecutor:
    """Deterministic inventory port fake for application and orchestration tests."""

    def __init__(self, results: Iterable[InventoryExecutionResult]) -> None:
        self._results = list(results)
        self.requests: list[InventoryExecutionRequest] = []

    def execute(self, request: InventoryExecutionRequest) -> InventoryExecutionResult:
        self.requests.append(request)
        if not self._results:
            raise RuntimeError("fake inventory executor has no queued result")
        return self._results.pop(0)


@dataclass(frozen=True, slots=True)
class InventoryExecutionOutcome:
    result: InventoryExecutionResult
    validation: InventoryObservationValidation
    discovery_result: InventoryDiscoveryResult
    refreshed_session: bytes | None = field(default=None, repr=False)


class InventoryExecutionService:
    """Invoke, validate, and close one positive-only inventory execution lease."""

    def __init__(
        self,
        executor: InventoryBrowserExecutor,
        lease_broker: InMemorySessionLeaseBroker,
        validator: InventoryObservationValidator | None = None,
    ) -> None:
        self._executor = executor
        self._lease_broker = lease_broker
        self._validator = validator or InventoryObservationValidator()

    def execute(self, request: InventoryExecutionRequest) -> InventoryExecutionOutcome:
        result: InventoryExecutionResult | None = None
        refreshed: bytes | None = None
        try:
            result = self._executor.execute(request)
            validation = self._validator.validate(request, result)
        finally:
            self._lease_broker.close(request.session_lease)
            refreshed = self._lease_broker.take_verified_refresh(request.session_lease)
        if result is None or not result.refreshed_session_eligible:
            refreshed = None
        return InventoryExecutionOutcome(
            result=result,
            validation=validation,
            discovery_result=validation.to_discovery_result(),
            refreshed_session=refreshed,
        )


class OwnerBoundAgenticInventoryExecution:
    """Build one account/session-bound request under caller-supplied residual limits."""

    def __init__(
        self,
        service: InventoryExecutionService,
        lease_broker: InMemorySessionLeaseBroker,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._service = service
        self._leases = lease_broker
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(
        self,
        *,
        owner_user_id: int,
        session_material: bytes,
        limits: ExecutionLimits | None = None,
        known_confirmation_ids: tuple[str, ...] = (),
    ) -> InventoryExecutionOutcome:
        execution_id = f"agentic-inventory-{uuid.uuid4().hex}"
        lease = self._leases.issue(
            owner_user_id=owner_user_id,
            subject_id=inventory_session_subject(owner_user_id),
            execution_id=execution_id,
            session_material=session_material,
        )
        now = self._clock()
        request = InventoryExecutionRequest(
            execution_id=execution_id,
            owner_user_id=owner_user_id,
            session_lease=lease,
            limits=limits or ExecutionLimits(deadline=now + timedelta(seconds=180)),
            known_confirmation_ids=known_confirmation_ids,
        )
        return self._service.execute(request)


def _terminal_failure(
    status: InventoryExecutionStatus,
) -> tuple[SynchronizationFailureCode, str]:
    if status in {
        InventoryExecutionStatus.SESSION_UNAVAILABLE,
        InventoryExecutionStatus.SIGNED_OUT,
        InventoryExecutionStatus.MFA_REQUIRED,
    }:
        return (
            SynchronizationFailureCode.AUTH_REQUIRED,
            "Booking.com account authentication is required.",
        )
    if status in {InventoryExecutionStatus.CAPTCHA, InventoryExecutionStatus.BOT_WALL}:
        return (
            SynchronizationFailureCode.BOT_WALL,
            "Booking.com presented a bot-verification wall; retry later.",
        )
    if status is InventoryExecutionStatus.VALIDATION_FAILURE:
        return (
            SynchronizationFailureCode.EXTRACTION_AMBIGUOUS,
            "Agentic inventory returned no valid positive reservation evidence.",
        )
    return (
        SynchronizationFailureCode.NAVIGATION_FAILED,
        "Agentic Booking.com inventory execution was unavailable; last-safe state was preserved.",
    )


def _traversal_claim_complete(
    scopes: tuple[ObservedInventoryScope, ...],
    reservations: tuple[ObservedReservation, ...],
) -> bool:
    by_scope = {scope.scope: scope for scope in scopes}
    if len(by_scope) != len(scopes) or frozenset(by_scope) != REQUIRED_INVENTORY_SCOPES:
        return False
    for scope, evidence in by_scope.items():
        visible = sum(item.scope is scope for item in reservations)
        if any(
            (
                evidence.completeness is not EvidenceCompleteness.COMPLETE,
                evidence.requested_scope_visible is not True,
                evidence.pagination_exhausted is not True,
                evidence.pages_observed < 1,
                evidence.visible_reservation_count != visible,
                visible == 0 and evidence.explicit_empty is not True,
                visible > 0 and evidence.explicit_empty is True,
            )
        ):
            return False
    return True


def _validated_unique_reservations(
    reservations: tuple[ObservedReservation, ...],
) -> tuple[tuple[ObservedReservation, ...], int, bool]:
    accepted: dict[str, ObservedReservation] = {}
    rejected = 0
    for candidate in reservations:
        if not _valid_positive(candidate):
            rejected += 1
            continue
        existing = accepted.get(candidate.remote_id)
        if existing is None:
            accepted[candidate.remote_id] = candidate
            continue
        merged = _merge_compatible(existing, candidate)
        if merged is None:
            return (), rejected + 2, True
        accepted[candidate.remote_id] = merged
    return tuple(accepted.values()), rejected, False


def _valid_positive(candidate: ObservedReservation) -> bool:
    if candidate.identity_evidence is not EvidenceCompleteness.COMPLETE:
        return False
    if candidate.completeness is EvidenceCompleteness.CONFLICTING:
        return False
    if candidate.lifecycle is ReservationLifecycle.ABSENT:
        return False
    allowed_lifecycles: dict[
        InventoryScope,
        set[ReservationLifecycle | None],
    ] = {
        InventoryScope.UPCOMING: {
            None,
            ReservationLifecycle.UNKNOWN,
            ReservationLifecycle.UPCOMING,
            ReservationLifecycle.CURRENT,
        },
        InventoryScope.PAST: {
            ReservationLifecycle.COMPLETED,
        },
        InventoryScope.CANCELLED: {
            ReservationLifecycle.CANCELLED,
        },
    }
    if candidate.lifecycle not in allowed_lifecycles[candidate.scope]:
        return False
    if candidate.all_in is AllInEvidence.CONFLICTING:
        return False
    if candidate.refundability is RefundabilityEvidence.CONFLICTING:
        return False
    if candidate.booked_total is None and candidate.all_in is AllInEvidence.EXPLICIT:
        return False
    return True


def _merge_compatible(
    left: ObservedReservation,
    right: ObservedReservation,
) -> ObservedReservation | None:
    if left.scope is not right.scope:
        return None
    left_lifecycle = (
        None if left.lifecycle is ReservationLifecycle.UNKNOWN else left.lifecycle
    )
    right_lifecycle = (
        None if right.lifecycle is ReservationLifecycle.UNKNOWN else right.lifecycle
    )
    lifecycle, compatible = _merge_optional(left_lifecycle, right_lifecycle)
    if not compatible:
        return None
    confirmation_id, compatible = _merge_optional(
        left.confirmation_id, right.confirmation_id
    )
    if not compatible:
        return None
    property_name, compatible = _merge_optional(left.property_name, right.property_name)
    if not compatible:
        return None
    property_reference, compatible = _merge_optional(
        left.property_reference, right.property_reference
    )
    if not compatible:
        return None
    check_in, compatible = _merge_optional(left.check_in, right.check_in)
    if not compatible:
        return None
    check_out, compatible = _merge_optional(left.check_out, right.check_out)
    if not compatible:
        return None
    room_type, compatible = _merge_optional(left.room_type, right.room_type)
    if not compatible:
        return None
    booked_total, compatible = _merge_optional(left.booked_total, right.booked_total)
    if not compatible:
        return None
    refundability_text, compatible = _merge_optional(
        left.refundability_text, right.refundability_text
    )
    if not compatible:
        return None
    refund_deadline, compatible = _merge_optional(
        left.refund_deadline, right.refund_deadline
    )
    if not compatible:
        return None
    occupancy, compatible = _merge_optional(left.occupancy, right.occupancy)
    if not compatible:
        return None
    all_in = _merge_evidence(left.all_in, right.all_in, AllInEvidence.UNKNOWN)
    refundability = _merge_evidence(
        left.refundability,
        right.refundability,
        RefundabilityEvidence.UNKNOWN,
    )
    if all_in is None or refundability is None:
        return None
    return replace(
        left,
        lifecycle=lifecycle,
        confirmation_id=confirmation_id,
        property_name=property_name,
        property_reference=property_reference,
        check_in=check_in,
        check_out=check_out,
        room_type=room_type,
        booked_total=booked_total,
        refundability_text=refundability_text,
        refund_deadline=refund_deadline,
        occupancy=occupancy,
        all_in=all_in,
        refundability=refundability,
        completeness=(
            EvidenceCompleteness.COMPLETE
            if left.completeness is right.completeness is EvidenceCompleteness.COMPLETE
            else EvidenceCompleteness.INCOMPLETE
        ),
    )


T = TypeVar("T")


def _merge_optional(left: T | None, right: T | None) -> tuple[T | None, bool]:
    if left is not None and right is not None and left != right:
        return None, False
    return (left if left is not None else right), True


def _merge_evidence(left: T, right: T, unknown: T) -> T | None:
    if left == right:
        return left
    if left == unknown:
        return right
    if right == unknown:
        return left
    return None


def _to_reservation_observation(
    observed: ObservedReservation,
    observed_at: datetime,
) -> ReservationObservation:
    refundable: bool | None = None
    refund_note = ""
    refund_deadline = None
    if observed.refundability is RefundabilityEvidence.EXPLICIT_REFUNDABLE:
        refundable = True
        refund_note = observed.refundability_text or ""
        refund_deadline = observed.refund_deadline
    elif observed.refundability is RefundabilityEvidence.EXPLICIT_NONREFUNDABLE:
        refundable = False
        refund_note = observed.refundability_text or ""
    return ReservationObservation(
        remote_id=observed.remote_id,
        lifecycle=observed.lifecycle or ReservationLifecycle.UNKNOWN,
        observed_at=observed_at,
        confirmation_id=observed.confirmation_id,
        property_name=observed.property_name,
        property_ref=observed.property_reference,
        check_in=observed.check_in,
        check_out=observed.check_out,
        room_type=observed.room_type,
        booked_total=(
            observed.booked_total
            if observed.all_in is AllInEvidence.EXPLICIT
            else None
        ),
        refundable=refundable,
        refund_note=refund_note,
        refund_deadline=refund_deadline,
        occupancy=observed.occupancy,
        source_url="",
        extraction_method="agentic_inventory",
    )
