from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from booksaver.application.browser_executor import (
    AgenticPriceExecutionService,
    ExecutionMeter,
    FakePriceBrowserExecutor,
    InMemorySessionLeaseBroker,
)
from booksaver.application.load_config import load_config
from booksaver.cli.commands import _make_agentic_price_executor, _make_check_coordinator
from booksaver.domain.agent import LLMUsage
from booksaver.domain.browser_executor import (
    AgenticBrowserSettings,
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionLimits,
    ExecutionRoutingMode,
    ExecutionUsage,
    InventoryExecutionRoutingMode,
    ObservationSource,
    ObservedOffer,
    ObservedQueryFacts,
    PriceExecutionRequest,
    PriceExecutionResult,
    PriceExecutionStatus,
    PriceExecutorKind,
    QualificationState,
    QualificationStatus,
    RedactedProvenance,
    RefundabilityEvidence,
    RoutingContext,
    RoutingReason,
    SessionLeaseReference,
    TrustedPriceQuery,
    ValidationRejection,
    resolve_execution_route,
    validate_price_observation,
)
from booksaver.domain.errors import ConfigValidationError
from booksaver.domain.model_policy import UsdAmount
from booksaver.domain.value_objects import Money, Occupancy, StayDates

NOW = datetime(2026, 8, 17, 3, tzinfo=UTC)


def _query() -> TrustedPriceQuery:
    return TrustedPriceQuery(
        property_name="Hotel Example",
        property_reference="booking-ref-123",
        stay_dates=StayDates(date(2026, 10, 2), date(2026, 10, 5)),
        occupancy=Occupancy(adults=2, children=1, rooms=1),
        currency="eur",
    )


def _lease() -> SessionLeaseReference:
    return SessionLeaseReference(
        lease_id="lease-1",
        owner_user_id=7,
        booking_id="booking-1",
        execution_id="execution-1",
        expires_at=NOW + timedelta(minutes=4),
    )


def _request(*, limits: ExecutionLimits | None = None) -> PriceExecutionRequest:
    return PriceExecutionRequest(
        execution_id="execution-1",
        owner_user_id=7,
        booking_id="booking-1",
        query=_query(),
        session_lease=_lease(),
        limits=limits or ExecutionLimits(deadline=NOW + timedelta(minutes=3)),
    )


def _facts() -> ObservedQueryFacts:
    query = _query()
    return ObservedQueryFacts(
        property_name="  HOTEL   Example ",
        property_reference=query.property_reference,
        check_in=query.stay_dates.check_in,
        check_out=query.stay_dates.check_out,
        occupancy=query.occupancy,
        currency="EUR",
        authenticated=True,
        genius=True,
        completeness=EvidenceCompleteness.COMPLETE,
    )


def _offer() -> ObservedOffer:
    return ObservedOffer(
        room_label="Standard Double Room",
        total=Money(Decimal("320.25"), "EUR"),
        all_in=AllInEvidence.EXPLICIT,
        refundability=RefundabilityEvidence.EXPLICIT_REFUNDABLE,
        refundability_text="Free cancellation until 1 October",
        completeness=EvidenceCompleteness.COMPLETE,
    )


def _result(
    *,
    facts: ObservedQueryFacts | None = None,
    offers: tuple[ObservedOffer, ...] | None = None,
    usage: ExecutionUsage | None = None,
) -> PriceExecutionResult:
    return PriceExecutionResult(
        status=PriceExecutionStatus.OBSERVED,
        query_facts=facts or _facts(),
        offers=offers or (_offer(),),
        provenance=RedactedProvenance(
            source=ObservationSource.FAKE,
            action_count=2,
            evidence_item_count=8,
        ),
        usage=usage or ExecutionUsage(total_actions=2),
        latency_ms=1200,
    )


def test_contract_has_no_session_or_content_payload_fields() -> None:
    forbidden = {
        "cookies",
        "session_material",
        "screenshot",
        "page_text",
        "accessibility_tree",
        "prompt",
        "reasoning",
    }
    contract_fields = {
        field.name
        for contract in (
            PriceExecutionRequest,
            PriceExecutionResult,
            ObservedQueryFacts,
            ObservedOffer,
            RedactedProvenance,
        )
        for field in fields(contract)
    }
    assert contract_fields.isdisjoint(forbidden)


def test_request_rejects_mismatched_session_binding() -> None:
    with pytest.raises(ValueError, match="lease binding"):
        replace(_request(), owner_user_id=8)


def test_non_observed_result_cannot_carry_observations() -> None:
    with pytest.raises(ValueError, match="non-observed"):
        PriceExecutionResult(
            status=PriceExecutionStatus.SIGNED_OUT,
            query_facts=_facts(),
        )


def test_observed_result_requires_facts_offers_and_provenance() -> None:
    with pytest.raises(ValueError, match="requires"):
        PriceExecutionResult(status=PriceExecutionStatus.OBSERVED)


def test_hard_limits_cannot_be_configured_above_approved_ceiling() -> None:
    with pytest.raises(ValueError, match="max_actions"):
        ExecutionLimits(deadline=NOW + timedelta(minutes=3), max_actions=16)
    with pytest.raises(ValueError, match="computer_use"):
        ExecutionLimits(deadline=NOW + timedelta(minutes=3), max_computer_use_actions=7)
    with pytest.raises(ValueError, match="USD 1.00"):
        ExecutionLimits(
            deadline=NOW + timedelta(minutes=3), max_job_cost=UsdAmount(1_000_001)
        )


def test_complete_observation_is_validated_without_equivalence_claim() -> None:
    validation = validate_price_observation(_request(), _result())
    assert validation.accepted
    assert validation.accepted_offers[0].room_label == "Standard Double Room"
    assert set(field.name for field in fields(validation.accepted_offers[0])) == {
        "room_label",
        "total",
        "cancellation_text",
    }


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        (
            replace(_facts(), completeness=EvidenceCompleteness.INCOMPLETE),
            ValidationRejection.QUERY_EVIDENCE_INCOMPLETE,
        ),
        (
            replace(_facts(), property_reference="other-ref"),
            ValidationRejection.PROPERTY_MISMATCH,
        ),
        (
            replace(_facts(), property_name="Different Hotel"),
            ValidationRejection.PROPERTY_MISMATCH,
        ),
        (
            replace(_facts(), check_out=date(2026, 10, 6)),
            ValidationRejection.DATE_MISMATCH,
        ),
        (
            replace(_facts(), occupancy=Occupancy(1)),
            ValidationRejection.OCCUPANCY_MISMATCH,
        ),
        (
            replace(_facts(), authenticated=None),
            ValidationRejection.AUTHENTICATION_REQUIRED,
        ),
        (
            replace(_facts(), currency="USD"),
            ValidationRejection.CURRENCY_MISMATCH,
        ),
    ],
)
def test_query_evidence_failures_are_closed(
    facts: ObservedQueryFacts, expected: ValidationRejection
) -> None:
    validation = validate_price_observation(_request(), _result(facts=facts))
    assert validation.rejection is expected
    assert validation.accepted_offers == ()


@pytest.mark.parametrize(
    "offer",
    [
        replace(_offer(), completeness=EvidenceCompleteness.INCOMPLETE),
        replace(_offer(), all_in=AllInEvidence.UNKNOWN),
        replace(
            _offer(), refundability=RefundabilityEvidence.EXPLICIT_NONREFUNDABLE
        ),
        replace(_offer(), refundability_text=None),
        replace(_offer(), total=Money(Decimal("320.25"), "USD")),
    ],
)
def test_incomplete_offer_evidence_is_never_accepted(offer: ObservedOffer) -> None:
    validation = validate_price_observation(_request(), _result(offers=(offer,)))
    assert validation.rejection is ValidationRejection.NO_COMPLETE_REFUNDABLE_ALL_IN_OFFER
    assert validation.rejected_offer_count == 1


def test_valid_offer_survives_alongside_rejected_offer() -> None:
    invalid = replace(_offer(), all_in=AllInEvidence.CONFLICTING)
    validation = validate_price_observation(
        _request(), _result(offers=(invalid, _offer()))
    )
    assert validation.accepted
    assert len(validation.accepted_offers) == 1
    assert validation.rejected_offer_count == 1


def test_result_over_action_or_cost_limit_is_rejected() -> None:
    usage = ExecutionUsage(total_actions=15, cost=UsdAmount(100_001))
    limits = ExecutionLimits(
        deadline=NOW + timedelta(minutes=3), max_job_cost=UsdAmount(100_000)
    )
    validation = validate_price_observation(_request(limits=limits), _result(usage=usage))
    assert validation.rejection is ValidationRejection.EXECUTION_LIMIT_BREACH


def test_meter_preserves_actual_billable_cost_when_provider_overshoots_cap() -> None:
    limits = ExecutionLimits(
        deadline=NOW + timedelta(minutes=3),
        max_job_cost=UsdAmount(100_000),
    )
    meter = ExecutionMeter(limits)

    with pytest.raises(RuntimeError, match="cost limit"):
        meter.record_model_call(LLMUsage(30_000, 4_096), UsdAmount(100_001))

    usage = meter.snapshot()
    assert usage.model_calls == 1
    assert usage.cost == UsdAmount(100_001)
    assert not usage.within(limits)


def _route_context(
    *,
    owner: bool = False,
    status: QualificationStatus = QualificationStatus.UNQUALIFIED,
    acknowledged: str | None = None,
) -> RoutingContext:
    qualified_at = NOW if status is QualificationStatus.QUALIFIED else None
    return RoutingContext(
        is_owner=owner,
        qualification=QualificationState(status=status, qualified_at=qualified_at),
        disclosure_version="disclosure-v1",
        acknowledged_disclosure_version=acknowledged,
    )


def test_routing_is_legacy_by_default_and_owner_only_in_canary() -> None:
    assert AgenticBrowserSettings().routing is ExecutionRoutingMode.LEGACY
    assert not resolve_execution_route(
        ExecutionRoutingMode.OWNER_CANARY, _route_context()
    ).use_agentic
    owner = resolve_execution_route(
        ExecutionRoutingMode.OWNER_CANARY, _route_context(owner=True)
    )
    assert owner.use_agentic
    assert owner.reason is RoutingReason.OWNER_CANARY


def test_consented_users_admits_owner_and_disclosed_invitee_before_qualification() -> None:
    owner = resolve_execution_route(
        ExecutionRoutingMode.CONSENTED_USERS,
        _route_context(owner=True),
    )
    invitee = resolve_execution_route(
        ExecutionRoutingMode.CONSENTED_USERS,
        _route_context(acknowledged="disclosure-v1"),
    )

    assert owner.use_agentic
    assert invitee.use_agentic
    assert owner.reason is RoutingReason.OWNER_CONSENTED_ROLLOUT
    assert invitee.reason is RoutingReason.INVITEE_CONSENTED_ROLLOUT


@pytest.mark.parametrize("acknowledged", [None, "disclosure-v0"])
def test_consented_users_requires_current_invitee_disclosure(
    acknowledged: str | None,
) -> None:
    decision = resolve_execution_route(
        ExecutionRoutingMode.CONSENTED_USERS,
        _route_context(acknowledged=acknowledged),
    )

    assert not decision.use_agentic
    assert decision.reason is RoutingReason.DISCLOSURE_REQUIRED


def test_invitee_agentic_requires_qualification_and_current_disclosure() -> None:
    unqualified = resolve_execution_route(
        ExecutionRoutingMode.AGENTIC, _route_context(acknowledged="disclosure-v1")
    )
    no_consent = resolve_execution_route(
        ExecutionRoutingMode.AGENTIC,
        _route_context(status=QualificationStatus.QUALIFIED),
    )
    admitted = resolve_execution_route(
        ExecutionRoutingMode.AGENTIC,
        _route_context(
            status=QualificationStatus.QUALIFIED, acknowledged="disclosure-v1"
        ),
    )
    assert unqualified.reason is RoutingReason.QUALIFICATION_REQUIRED
    assert no_consent.reason is RoutingReason.DISCLOSURE_REQUIRED
    assert admitted.use_agentic


def test_invitee_agentic_rejects_qualification_from_another_executor_policy() -> None:
    context = _route_context(
        status=QualificationStatus.QUALIFIED,
        acknowledged="disclosure-v1",
    )
    context = replace(
        context,
        qualification=QualificationState(
            status=QualificationStatus.QUALIFIED,
            policy_version="agentic-price-v1",
            qualified_at=NOW,
        ),
    )

    decision = resolve_execution_route(ExecutionRoutingMode.AGENTIC, context)

    assert decision.use_agentic is False
    assert decision.reason is RoutingReason.QUALIFICATION_REQUIRED


def test_owner_agentic_mode_still_requires_completed_qualification() -> None:
    blocked = resolve_execution_route(
        ExecutionRoutingMode.AGENTIC,
        _route_context(owner=True),
    )
    admitted = resolve_execution_route(
        ExecutionRoutingMode.AGENTIC,
        _route_context(owner=True, status=QualificationStatus.QUALIFIED),
    )

    assert not blocked.use_agentic
    assert blocked.reason is RoutingReason.QUALIFICATION_REQUIRED
    assert admitted.use_agentic
    assert admitted.reason is RoutingReason.OWNER_AGENTIC


@pytest.mark.parametrize(
    "mode",
    [ExecutionRoutingMode.AGENTIC, ExecutionRoutingMode.CONSENTED_USERS],
)
def test_regression_forces_legacy_even_for_owner(mode: ExecutionRoutingMode) -> None:
    decision = resolve_execution_route(
        mode,
        _route_context(owner=True, status=QualificationStatus.REGRESSED),
    )
    assert not decision.use_agentic
    assert decision.reason is RoutingReason.REGRESSION_ROLLBACK


class _RestoreTarget:
    def __init__(self) -> None:
        self.restored: list[bytes] = []

    def restore_session(self, data: bytes) -> None:
        self.restored.append(data)


class _RefreshSource:
    def __init__(self, *, verified: bool) -> None:
        self.verified = verified

    def verify_authenticated_account(self) -> bool:
        return self.verified

    def capture_session(self) -> bytes:
        return b"refreshed-secret"


def _issued_broker() -> tuple[InMemorySessionLeaseBroker, SessionLeaseReference]:
    broker = InMemorySessionLeaseBroker(clock=lambda: NOW)
    reference = broker.issue(
        owner_user_id=7,
        booking_id="booking-1",
        execution_id="execution-1",
        session_material=b"original-secret",
    )
    return broker, reference


def test_session_lease_is_single_use_and_secret_is_not_in_repr() -> None:
    broker, reference = _issued_broker()
    assert "original-secret" not in repr(broker)
    target = _RestoreTarget()
    broker.restore_into(reference, target)
    assert target.restored == [b"original-secret"]
    with pytest.raises(ValueError, match="no longer consumable"):
        broker.restore_into(reference, target)


def test_refresh_requires_code_owned_authentication_verification() -> None:
    broker, reference = _issued_broker()
    broker.restore_into(reference, _RestoreTarget())
    assert not broker.capture_verified_refresh(reference, _RefreshSource(verified=False))
    assert broker.take_verified_refresh(reference) is None
    assert broker.capture_verified_refresh(reference, _RefreshSource(verified=True))
    broker.close(reference)
    assert broker.take_verified_refresh(reference) == b"refreshed-secret"
    assert broker.active_count() == 0


def test_execution_service_closes_lease_on_executor_exception() -> None:
    broker, issued = _issued_broker()
    request = replace(_request(), session_lease=issued)
    executor = FakePriceBrowserExecutor([])
    service = AgenticPriceExecutionService(executor, broker)
    with pytest.raises(RuntimeError, match="no queued"):
        service.execute(request)
    assert broker.active_count() == 0


def test_execution_meter_counts_computer_use_inside_total_and_caps_cost() -> None:
    limits = ExecutionLimits(
        deadline=NOW + timedelta(minutes=3),
        max_actions=2,
        max_computer_use_actions=1,
        max_job_cost=UsdAmount(10),
    )
    meter = ExecutionMeter(limits)
    meter.record_action()
    meter.record_action(computer_use=True)
    meter.record_model_call(LLMUsage(1, 2), UsdAmount(10))
    assert meter.snapshot() == ExecutionUsage(
        model_calls=1,
        total_actions=2,
        computer_use_actions=1,
        tokens=LLMUsage(1, 2),
        cost=UsdAmount(10),
    )
    with pytest.raises(RuntimeError, match="action limit"):
        meter.record_action()
    with pytest.raises(RuntimeError, match="cost limit"):
        meter.record_model_call(LLMUsage(), UsdAmount(1))


class _ConfigSource:
    def __init__(
        self,
        routing: str | None = None,
        inventory_routing: str | None = None,
        price_executor: str | None = None,
    ) -> None:
        self.routing = routing
        self.inventory_routing = inventory_routing
        self.price_executor = price_executor

    def read(self) -> dict[str, object]:
        data: dict[str, object] = {
            "storage": {"data_directory": "/tmp/booksaver-test"}
        }
        agentic_browser: dict[str, str] = {}
        if self.routing is not None:
            agentic_browser["routing"] = self.routing
        if self.inventory_routing is not None:
            agentic_browser["inventory_routing"] = self.inventory_routing
        if self.price_executor is not None:
            agentic_browser["price_executor"] = self.price_executor
        if agentic_browser:
            data["agentic_browser"] = agentic_browser
        return data


def test_config_defaults_agentic_browser_to_legacy() -> None:
    settings = load_config(_ConfigSource()).agentic_browser_settings
    assert settings.routing is ExecutionRoutingMode.LEGACY
    assert settings.inventory_routing is InventoryExecutionRoutingMode.AGENTIC
    assert settings.price_executor is PriceExecutorKind.BROWSER_USE


def test_config_inventory_routing_is_independent_from_price() -> None:
    settings = load_config(
        _ConfigSource(routing="owner_canary", inventory_routing="legacy")
    ).agentic_browser_settings

    assert settings.routing is ExecutionRoutingMode.OWNER_CANARY
    assert settings.inventory_routing is InventoryExecutionRoutingMode.LEGACY


def test_config_accepts_consented_users_price_routing() -> None:
    settings = load_config(_ConfigSource(routing="consented_users")).agentic_browser_settings

    assert settings.routing is ExecutionRoutingMode.CONSENTED_USERS


def test_config_rejects_unknown_agentic_routing() -> None:
    with pytest.raises(ConfigValidationError, match="agentic_browser.routing"):
        load_config(_ConfigSource("maybe"))


def test_config_rejects_owner_canary_inventory_routing() -> None:
    with pytest.raises(ConfigValidationError, match="agentic_browser.inventory_routing"):
        load_config(_ConfigSource(inventory_routing="owner_canary"))


def test_config_accepts_stagehand_as_explicit_price_rollback() -> None:
    settings = load_config(_ConfigSource(price_executor="stagehand")).agentic_browser_settings

    assert settings.price_executor is PriceExecutorKind.STAGEHAND


def test_config_rejects_unknown_price_executor() -> None:
    with pytest.raises(ConfigValidationError, match="agentic_browser.price_executor"):
        load_config(_ConfigSource(price_executor="automatic"))


def test_shared_price_factory_defaults_browser_use_and_keeps_stagehand_rollback() -> None:
    from booksaver.infrastructure.browser.agentic_executor import LocalAgenticPriceExecutor
    from booksaver.infrastructure.browser.browser_use_price_executor import (
        LocalBrowserUsePriceExecutor,
    )

    broker = InMemorySessionLeaseBroker()
    browser_use = _make_agentic_price_executor(
        load_config(_ConfigSource()),
        "test-key",
        object(),
        broker,
    )
    stagehand = _make_agentic_price_executor(
        load_config(_ConfigSource(price_executor="stagehand")),
        "test-key",
        object(),
        broker,
    )

    assert isinstance(browser_use, LocalBrowserUsePriceExecutor)
    assert isinstance(stagehand, LocalAgenticPriceExecutor)


def test_production_composition_uses_browser_use_for_every_agentic_inventory_trigger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from booksaver.infrastructure.browser.browser_use_inventory_executor import (
        LocalBrowserUseInventoryExecutor,
    )

    cfg = load_config(_ConfigSource())
    cfg.data_directory = type(cfg.data_directory)(tmp_path)
    monkeypatch.setenv("BOOKSAVER_LLM_API_KEY", "test-key")
    coordinator = _make_check_coordinator(cfg, object())
    regular = coordinator._agentic_inventory_executor_factory  # noqa: SLF001
    bookings = coordinator._bookings_inventory_executor_factory  # noqa: SLF001
    assert regular is not None and bookings is not None
    broker = InMemorySessionLeaseBroker()

    assert isinstance(regular(object(), broker), LocalBrowserUseInventoryExecutor)
    assert isinstance(bookings(object(), broker), LocalBrowserUseInventoryExecutor)
