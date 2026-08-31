from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from booksaver.application.browser_executor import (
    AgenticPriceExecutionService,
    FakePriceBrowserExecutor,
    InMemorySessionLeaseBroker,
    OwnerBoundAgenticPriceCheck,
)
from booksaver.application.inventory_executor import (
    FakeInventoryBrowserExecutor,
    InventoryExecutionService,
    InventoryObservationValidator,
    InventoryValidationFailure,
    OwnerBoundAgenticInventoryExecution,
)
from booksaver.domain.account_sync import (
    InventoryCompleteness,
    ReservationLifecycle,
    SynchronizationFailureCode,
)
from booksaver.domain.browser_executor import (
    AgenticBrowserSettings,
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionLimits,
    ExecutionUsage,
    InventoryExecutionRoutingMode,
    ObservationSource,
    PriceExecutionResult,
    PriceExecutionStatus,
    RedactedProvenance,
    RefundabilityEvidence,
    SessionLeaseReference,
)
from booksaver.domain.inventory_executor import (
    InventoryExecutionRequest,
    InventoryExecutionResult,
    InventoryExecutionStatus,
    InventoryScope,
    KnownInventoryReservation,
    ObservedInventoryScope,
    ObservedReservation,
    inventory_session_subject,
)
from booksaver.domain.models import Booking
from booksaver.domain.value_objects import (
    ConfirmationId,
    Money,
    Occupancy,
    Platform,
    ProductType,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
)

NOW = datetime(2026, 8, 25, 18, tzinfo=UTC)


def _lease(*, subject_id: str = "account:7") -> SessionLeaseReference:
    return SessionLeaseReference(
        lease_id="inventory-lease-1",
        owner_user_id=7,
        subject_id=subject_id,
        execution_id="inventory-execution-1",
        expires_at=NOW + timedelta(minutes=4),
    )


def _request(*, limits: ExecutionLimits | None = None) -> InventoryExecutionRequest:
    return InventoryExecutionRequest(
        execution_id="inventory-execution-1",
        owner_user_id=7,
        session_lease=_lease(),
        limits=limits or ExecutionLimits(deadline=NOW + timedelta(minutes=3)),
    )


def test_inventory_request_bounds_and_redacts_known_confirmation_hints() -> None:
    known = KnownInventoryReservation(
        confirmation_id="ABC123",
        property_name="Hotel Example",
        check_in=date(2026, 11, 24),
        check_out=date(2026, 11, 25),
    )
    request = replace(
        _request(),
        known_confirmation_ids=("ABC123", "6992391225"),
        known_reservations=(known,),
    )

    assert request.known_confirmation_ids == ("ABC123", "6992391225")
    assert "ABC123" not in repr(request)
    assert "Hotel Example" not in repr(request)
    with pytest.raises(ValueError, match="unique"):
        replace(request, known_confirmation_ids=("ABC123", "ABC123"))
    with pytest.raises(ValueError, match="bounded machine identifier"):
        replace(request, known_confirmation_ids=("not a safe confirmation",))
    with pytest.raises(ValueError, match="bounded inventory hint"):
        replace(request, known_confirmation_ids=tuple(f"ID-{index}" for index in range(26)))
    with pytest.raises(ValueError, match="known reservations exceed"):
        replace(request, known_reservations=(known,) * 26)


def _scope(
    scope: InventoryScope,
    *,
    count: int,
    empty: bool,
) -> ObservedInventoryScope:
    return ObservedInventoryScope(
        scope=scope,
        requested_scope_visible=True,
        explicit_empty=empty,
        pagination_exhausted=True,
        pages_observed=1,
        visible_reservation_count=count,
        detail_count=count,
        completeness=EvidenceCompleteness.COMPLETE,
    )


def _reservation(**changes: object) -> ObservedReservation:
    base = ObservedReservation(
        remote_id="trip-123",
        identity_evidence=EvidenceCompleteness.COMPLETE,
        scope=InventoryScope.UPCOMING,
        lifecycle=ReservationLifecycle.UPCOMING,
        confirmation_id="ABC123",
        property_name="Hotel Example",
        property_reference="hotel-example-ref",
        check_in=date(2026, 11, 1),
        check_out=date(2026, 11, 3),
        room_type="King Room",
        booked_total=Money(Decimal("301"), "USD"),
        all_in=AllInEvidence.EXPLICIT,
        refundability=RefundabilityEvidence.EXPLICIT_REFUNDABLE,
        refundability_text="Free cancellation until 30 October",
        refund_deadline=date(2026, 10, 30),
        occupancy=Occupancy(2, 0, 1),
        completeness=EvidenceCompleteness.COMPLETE,
    )
    return replace(base, **changes)


def _result(
    *,
    reservations: tuple[ObservedReservation, ...] | None = None,
    usage: ExecutionUsage | None = None,
    refreshed: bool = False,
) -> InventoryExecutionResult:
    observed = reservations if reservations is not None else (_reservation(),)
    return InventoryExecutionResult(
        status=InventoryExecutionStatus.OBSERVED,
        authenticated=True,
        scopes=(
            _scope(
                InventoryScope.UPCOMING,
                count=sum(item.scope is InventoryScope.UPCOMING for item in observed),
                empty=not any(item.scope is InventoryScope.UPCOMING for item in observed),
            ),
            _scope(
                InventoryScope.PAST,
                count=sum(item.scope is InventoryScope.PAST for item in observed),
                empty=not any(item.scope is InventoryScope.PAST for item in observed),
            ),
            _scope(
                InventoryScope.CANCELLED,
                count=sum(item.scope is InventoryScope.CANCELLED for item in observed),
                empty=not any(item.scope is InventoryScope.CANCELLED for item in observed),
            ),
        ),
        reservations=observed,
        provenance=RedactedProvenance(
            source=ObservationSource.FAKE,
            action_count=2,
            evidence_item_count=15,
            schema_version="inventory-observation-v1",
        ),
        refreshed_session_eligible=refreshed,
        usage=usage or ExecutionUsage(total_actions=2),
        latency_ms=1200,
    )


def test_inventory_contract_excludes_session_and_page_content_fields() -> None:
    forbidden = {
        "cookies",
        "session_material",
        "screenshot",
        "page_text",
        "accessibility_tree",
        "selector",
        "prompt",
        "reasoning",
        "eligibility",
        "absence",
    }
    request_fields = {item.name for item in fields(InventoryExecutionRequest)}
    result_fields = {item.name for item in fields(InventoryExecutionResult)}
    reservation_fields = {item.name for item in fields(ObservedReservation)}
    assert forbidden.isdisjoint(request_fields | result_fields | reservation_fields)


def test_inventory_request_requires_exact_account_subject_and_scopes() -> None:
    assert inventory_session_subject(7) == "account:7"
    with pytest.raises(ValueError, match="binding"):
        replace(_request(), session_lease=_lease(subject_id="booking-1"))
    with pytest.raises(ValueError, match="upcoming, past, and cancelled"):
        replace(_request(), required_scopes=frozenset({InventoryScope.UPCOMING}))


def test_session_reference_supports_neutral_subject_and_price_alias() -> None:
    lease = _lease()
    assert lease.subject_id == "account:7"
    assert lease.booking_id == "account:7"
    legacy = SessionLeaseReference(
        lease_id="price-lease",
        owner_user_id=7,
        booking_id="booking-1",
        execution_id="price-execution",
        expires_at=NOW + timedelta(minutes=4),
    )
    assert legacy.subject_id == "booking-1"


def test_inventory_routing_defaults_agentic_and_is_independent_from_price() -> None:
    settings = AgenticBrowserSettings()
    assert settings.inventory_routing is InventoryExecutionRoutingMode.AGENTIC
    assert InventoryExecutionRoutingMode.parse("legacy") is (
        InventoryExecutionRoutingMode.LEGACY
    )
    with pytest.raises(ValueError, match="inventory_routing"):
        InventoryExecutionRoutingMode.parse("owner_canary")


def test_validator_maps_only_positive_facts_and_never_authorizes_absence() -> None:
    validation = InventoryObservationValidator(clock=lambda: NOW).validate(
        _request(), _result()
    )
    assert validation.traversal_claim_complete
    assert validation.accepted_positive_count == 1
    observation = validation.observations[0]
    assert observation.lifecycle is ReservationLifecycle.UPCOMING
    assert observation.booked_total == Money(Decimal("301"), "USD")
    assert observation.refundable is True
    assert observation.extraction_method == "agentic_inventory"

    discovery = validation.to_discovery_result()
    assert discovery.completeness is InventoryCompleteness.INCOMPLETE
    assert discovery.observations == (observation,)
    assert discovery.failure_code is None


def test_unknown_or_incomplete_facts_remain_ineligible_or_are_rejected() -> None:
    unknown_details = _reservation(
        remote_id="trip-unknown",
        booked_total=Money(Decimal("301"), "USD"),
        all_in=AllInEvidence.UNKNOWN,
        refundability=RefundabilityEvidence.UNKNOWN,
        refundability_text=None,
        refund_deadline=None,
        completeness=EvidenceCompleteness.INCOMPLETE,
    )
    missing_identity = _reservation(
        remote_id="trip-unverified",
        identity_evidence=EvidenceCompleteness.INCOMPLETE,
    )
    validation = InventoryObservationValidator(clock=lambda: NOW).validate(
        _request(), _result(reservations=(unknown_details, missing_identity))
    )
    assert validation.accepted_positive_count == 1
    assert validation.rejected_reservation_count == 1
    assert validation.observations[0].booked_total is None
    assert validation.observations[0].refundable is None
    assert validation.to_discovery_result().failure_code is (
        SynchronizationFailureCode.EXTRACTION_AMBIGUOUS
    )


@pytest.mark.parametrize("scope", [InventoryScope.PAST, InventoryScope.CANCELLED])
@pytest.mark.parametrize("lifecycle", [None, ReservationLifecycle.UNKNOWN])
def test_non_upcoming_scope_requires_explicit_terminal_lifecycle(
    scope: InventoryScope,
    lifecycle: ReservationLifecycle | None,
) -> None:
    candidate = _reservation(scope=scope, lifecycle=lifecycle)

    validation = InventoryObservationValidator(clock=lambda: NOW).validate(
        _request(), _result(reservations=(candidate,))
    )

    assert validation.accepted_positive_count == 0
    assert validation.rejected_reservation_count == 1
    assert validation.to_discovery_result().observations == ()


@pytest.mark.parametrize(
    ("clock", "latency_ms"),
    [
        (NOW + timedelta(minutes=3), 1_200),
        (NOW, 180_001),
    ],
)
def test_validator_rejects_results_at_deadline_or_over_timeout(
    clock: datetime,
    latency_ms: int,
) -> None:
    validation = InventoryObservationValidator(clock=lambda: clock).validate(
        _request(), replace(_result(), latency_ms=latency_ms)
    )

    assert validation.failure is InventoryValidationFailure.EXECUTION_LIMIT_BREACH
    assert validation.observations == ()


def test_conflicting_duplicate_identity_fails_the_whole_observation() -> None:
    conflict = _reservation(property_name="Different Hotel")
    validation = InventoryObservationValidator(clock=lambda: NOW).validate(
        _request(), _result(reservations=(_reservation(), conflict))
    )
    assert validation.failure is InventoryValidationFailure.IDENTITY_AMBIGUOUS
    assert validation.failure_code is SynchronizationFailureCode.IDENTITY_AMBIGUOUS
    assert not validation.observations
    assert validation.to_discovery_result().completeness is InventoryCompleteness.FAILED


def test_limits_and_closed_terminal_states_fail_without_positive_content() -> None:
    limits = ExecutionLimits(
        deadline=NOW + timedelta(minutes=3),
        max_actions=1,
        max_computer_use_actions=1,
    )
    over_limit = InventoryObservationValidator(clock=lambda: NOW).validate(
        _request(limits=limits),
        _result(usage=ExecutionUsage(total_actions=2)),
    )
    assert over_limit.failure is InventoryValidationFailure.EXECUTION_LIMIT_BREACH

    signed_out = InventoryObservationValidator(clock=lambda: NOW).validate(
        _request(), InventoryExecutionResult(InventoryExecutionStatus.SIGNED_OUT)
    )
    assert signed_out.failure_code is SynchronizationFailureCode.AUTH_REQUIRED


def test_inventory_service_closes_lease_when_executor_raises() -> None:
    broker = InMemorySessionLeaseBroker(clock=lambda: NOW)
    lease = broker.issue(
        owner_user_id=7,
        subject_id="account:7",
        execution_id="inventory-execution-1",
        session_material=b"secret-session",
    )
    request = replace(_request(), session_lease=lease)
    service = InventoryExecutionService(FakeInventoryBrowserExecutor([]), broker)
    with pytest.raises(RuntimeError, match="no queued result"):
        service.execute(request)
    assert broker.active_count() == 0


def test_owner_bound_inventory_uses_supplied_residual_limits() -> None:
    broker = InMemorySessionLeaseBroker(clock=lambda: NOW)
    fake = FakeInventoryBrowserExecutor([_result()])
    execution = OwnerBoundAgenticInventoryExecution(
        InventoryExecutionService(
            fake,
            broker,
            InventoryObservationValidator(clock=lambda: NOW),
        ),
        broker,
        clock=lambda: NOW,
    )
    limits = ExecutionLimits(
        deadline=NOW + timedelta(seconds=37),
        max_actions=4,
        max_computer_use_actions=2,
    )
    outcome = execution.execute(
        owner_user_id=7,
        session_material=b"secret-session",
        limits=limits,
        known_confirmation_ids=("ABC123",),
        known_reservations=(
            KnownInventoryReservation(
                confirmation_id="ABC123",
                property_name="Hotel Example",
                check_in=date(2026, 11, 24),
                check_out=date(2026, 11, 25),
            ),
        ),
    )
    assert outcome.discovery_result.completeness is InventoryCompleteness.INCOMPLETE
    assert fake.requests[0].limits is limits
    assert fake.requests[0].session_lease.subject_id == "account:7"
    assert fake.requests[0].known_confirmation_ids == ("ABC123",)
    assert fake.requests[0].known_reservations[0].confirmation_id == "ABC123"
    assert broker.active_count() == 0


def test_owner_bound_price_accepts_same_outer_residual_limits() -> None:
    broker = InMemorySessionLeaseBroker(clock=lambda: NOW)
    fake = FakePriceBrowserExecutor(
        [PriceExecutionResult(PriceExecutionStatus.PROVIDER_FAILURE)]
    )
    execution = OwnerBoundAgenticPriceCheck(
        AgenticPriceExecutionService(fake, broker),
        broker,
        clock=lambda: NOW,
    )
    booking = Booking.create(
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId.of("ABC123"),
        property=Property("Hotel Example", "hotel-example-ref"),
        stay_dates=StayDates(date(2026, 11, 1), date(2026, 11, 3)),
        room_type=RoomType("King Room"),
        baseline_price=Money(Decimal("301"), "USD"),
        refundability=RefundabilityPolicy(True, "Free cancellation"),
        registered_at=NOW,
        occupancy=Occupancy(2, 0, 1),
    )
    limits = ExecutionLimits(
        deadline=NOW + timedelta(seconds=22),
        max_actions=3,
        max_computer_use_actions=3,
    )
    execution.execute(
        owner_user_id=7,
        booking=booking,
        session_material=b"secret-session",
        limits=limits,
    )
    assert fake.requests[0].limits is limits
    assert fake.requests[0].session_lease.subject_id == booking.booking_id
