from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from booksaver.application.async_runner import AsyncLoopRunner
from booksaver.application.browser_executor import InMemorySessionLeaseBroker
from booksaver.application.model_policy import BrowserJobCostBudget
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionLimits,
    ExecutorSafetyViolation,
    ObservationSource,
    ObservedOffer,
    ObservedQueryFacts,
    PriceExecutionRequest,
    PriceExecutionStatus,
    RefundabilityEvidence,
    TrustedPriceQuery,
)
from booksaver.domain.model_policy import (
    AdmissionDecision,
    BrowserJobKind,
    CallerKeyRef,
    CostReconciliation,
    CostReservation,
    ModelCostEstimator,
    ReservationStatus,
)
from booksaver.domain.value_objects import Money, Occupancy, StayDates
from booksaver.infrastructure.browser.agentic_executor import (
    TypedObservation,
    build_trusted_search_url,
)
from booksaver.infrastructure.browser.browser_use_inventory_executor import (
    BrowserUseActionGuard,
)
from booksaver.infrastructure.browser.browser_use_price_executor import (
    BrowserUsePriceBrowserExecutor,
    BrowserUsePriceObservationSubmission,
    BrowserUsePriceOfferSubmission,
    BrowserUsePriceQuerySubmission,
    BrowserUsePriceRuntimeResult,
    BrowserUsePriceTerminalSubmission,
    GuardedTrustedType,
    _observation_from_state,
    _price_agent_task,
    _price_entry_url,
    _PriceEpisodeState,
    _terminal_status,
    _trusted_input_node_allowed,
    _typed_observation_error_code,
)


class _Ledger:
    def reserve_call(self, request: Any) -> AdmissionDecision:
        return AdmissionDecision(
            reservation=CostReservation(
                request.reservation_id,
                request.job_id,
                request.utc_date,
                request.profile,
                request.reserved_cost,
                ReservationStatus.RESERVED,
            )
        )

    def reconcile_call(self, request: Any) -> CostReconciliation:
        return CostReconciliation(
            request.reservation_id,
            request.charged_cost,
            ReservationStatus.CHARGED,
        )

    def list_attempts(self, _job_id: str) -> tuple[object, ...]:
        return ()


def _budget() -> BrowserJobCostBudget:
    return BrowserJobCostBudget(
        job_id="browser-use-price-job",
        job_kind=BrowserJobKind.CHECK_NOW,
        caller_key_ref=CallerKeyRef(7, "owner", "deployment_key"),
        ledger=_Ledger(),  # type: ignore[arg-type]
        estimator=ModelCostEstimator(),
        preserve_opus_diagnostic=False,
        clock=lambda: datetime(2026, 9, 2, 12, tzinfo=UTC),
    )


def _request(broker: InMemorySessionLeaseBroker) -> PriceExecutionRequest:
    execution_id = "browser-use-price-1"
    lease = broker.issue(
        owner_user_id=7,
        booking_id="booking-1",
        execution_id=execution_id,
        session_material=b'[{"name":"session","value":"secret","domain":".booking.com"}]',
    )
    return PriceExecutionRequest(
        execution_id=execution_id,
        owner_user_id=7,
        booking_id="booking-1",
        query=TrustedPriceQuery(
            property_name="Hotel Example",
            property_reference="Hotel Example",
            stay_dates=StayDates(
                check_in=datetime(2026, 11, 24).date(),
                check_out=datetime(2026, 11, 25).date(),
            ),
            occupancy=Occupancy(adults=2, children=0, rooms=1),
            currency="USD",
        ),
        session_lease=lease,
        limits=ExecutionLimits(deadline=datetime.now(UTC) + timedelta(minutes=3)),
    )


def _observation() -> TypedObservation:
    return TypedObservation(
        facts=ObservedQueryFacts(
            property_name="Hotel Example",
            property_reference="https://www.booking.com/hotel/us/example.html",
            check_in=datetime(2026, 11, 24).date(),
            check_out=datetime(2026, 11, 25).date(),
            occupancy=Occupancy(2, 0, 1),
            currency="USD",
            authenticated=True,
            genius=True,
            completeness=EvidenceCompleteness.COMPLETE,
        ),
        offers=(
            ObservedOffer(
                room_label="Deluxe King Room",
                total=Money(Decimal("275.00"), "USD"),
                all_in=AllInEvidence.EXPLICIT,
                refundability=RefundabilityEvidence.EXPLICIT_REFUNDABLE,
                refundability_text="Free cancellation until November 23",
                completeness=EvidenceCompleteness.COMPLETE,
            ),
        ),
        evidence_item_count=15,
    )


class _Runtime:
    def __init__(self, result: BrowserUsePriceRuntimeResult) -> None:
        self.result = result
        self.restored: bytes | None = None
        self.closed = False

    def restore_session(self, data: bytes) -> None:
        self.restored = data

    async def execute(self, *_args: object, **_kwargs: object) -> BrowserUsePriceRuntimeResult:
        return self.result

    async def close(self) -> None:
        self.closed = True


def test_price_submission_maps_to_existing_typed_contract() -> None:
    state = _PriceEpisodeState(
        query=BrowserUsePriceQuerySubmission(
            property_name="Hotel Example",
            check_in="2026-11-24",
            check_out="2026-11-25",
            adults="2",
            children="0",
            rooms="1",
            currency="USD",
            genius="true",
            completeness="complete",
        ),
        property_reference="https://www.booking.com/hotel/us/example.html",
        offers=[
            BrowserUsePriceOfferSubmission(
                room_label="Deluxe King Room",
                total="275.00",
                currency="USD",
                all_in="explicit",
                refundability="explicit_refundable",
                refundability_text="Free cancellation until November 23",
                completeness="complete",
            )
        ],
    )

    observation = _observation_from_state(state)

    assert observation.facts.authenticated is True
    assert observation.facts.genius is True
    assert observation.offers[0].total.amount == Decimal("275.00")
    assert observation.offers[0].refundability is (
        RefundabilityEvidence.EXPLICIT_REFUNDABLE
    )


def test_price_submission_canonicalizes_property_reference_without_query() -> None:
    state = _PriceEpisodeState(
        query=BrowserUsePriceQuerySubmission(
            property_name="Hotel Example",
            check_in="2026-11-24",
            check_out="2026-11-25",
            adults="2",
            children="0",
            rooms="1",
            currency="USD",
            genius="true",
            completeness="complete",
        ),
        property_reference=(
            "https://www.booking.com/hotel/us/example.html?"
            + "opaque_tracking_value="
            + "x" * 400
        ),
        offers=[
            BrowserUsePriceOfferSubmission(
                room_label="Deluxe King Room",
                total="275.00",
                currency="USD",
                all_in="explicit",
                refundability="explicit_refundable",
                refundability_text="Free cancellation until November 23",
                completeness="complete",
            )
        ],
    )

    observation = _observation_from_state(state)

    assert (
        observation.facts.property_reference
        == "https://www.booking.com/hotel/us/example.html"
    )


def test_price_action_schemas_are_strict_and_all_required() -> None:
    query_schema = BrowserUsePriceQuerySubmission.model_json_schema()
    offer_schema = BrowserUsePriceOfferSubmission.model_json_schema()
    terminal_schema = BrowserUsePriceTerminalSubmission.model_json_schema()
    observation_schema = BrowserUsePriceObservationSubmission.model_json_schema()

    assert set(query_schema["required"]) == set(query_schema["properties"])
    assert set(offer_schema["required"]) == set(offer_schema["properties"])
    assert terminal_schema["required"] == ["success", "status"]
    assert query_schema["additionalProperties"] is False
    assert offer_schema["additionalProperties"] is False
    assert "offers" in observation_schema["required"]
    assert observation_schema["properties"]["offers"]["minItems"] == 1
    assert set(query_schema["properties"]["completeness"]["enum"]) == {
        "complete",
        "incomplete",
        "conflicting",
    }
    assert set(offer_schema["properties"]["refundability"]["enum"]) == {
        "explicit_refundable",
        "explicit_nonrefundable",
        "unknown",
        "conflicting",
    }


def test_price_action_schemas_reject_ambiguous_evidence_labels() -> None:
    with pytest.raises(ValidationError):
        BrowserUsePriceOfferSubmission(
            room_label="Deluxe King Room",
            total="275.00",
            currency="USD",
            all_in="yes",  # type: ignore[arg-type]
            refundability="refundable",  # type: ignore[arg-type]
            refundability_text="Free cancellation until November 23",
            completeness="complete",
        )


def test_typed_observation_error_is_reduced_to_privacy_safe_code() -> None:
    state = _PriceEpisodeState(
        query=BrowserUsePriceQuerySubmission(
            property_name="Hotel Example",
            check_in="not-a-date",
            check_out="2026-11-25",
            adults="2",
            children="0",
            rooms="1",
            currency="USD",
            genius="true",
            completeness="complete",
        ),
        property_reference="https://www.booking.com/hotel/us/example.html",
        offers=[
            BrowserUsePriceOfferSubmission(
                room_label="Deluxe King Room",
                total="275.00",
                currency="USD",
                all_in="explicit",
                refundability="explicit_refundable",
                refundability_text="Free cancellation until November 23",
                completeness="complete",
            )
        ],
    )
    with pytest.raises(ValueError) as captured:
        _observation_from_state(state)

    assert _typed_observation_error_code(captured.value) == "stay_dates"


def test_trusted_type_requires_safe_visible_input_and_exact_bounded_shape() -> None:
    class _Node:
        target_id = "active"
        is_visible = True
        node_name = "input"
        attributes = {
            "type": "date",
            "name": "checkin",
            "aria-label": "Check-in date",
        }

        @staticmethod
        def get_meaningful_text_for_llm() -> str:
            return "Check-in date"

    assert GuardedTrustedType(index=4, value="2026-11-24")
    assert _trusted_input_node_allowed(
        BrowserUseActionGuard(),
        node=_Node(),
        current_url="https://www.booking.com/searchresults.html?checkin=2026-11-24",
        active_target_id="active",
    )

    password = _Node()
    password.attributes = {"type": "password", "name": "password"}
    assert not _trusted_input_node_allowed(
        BrowserUseActionGuard(),
        node=password,
        current_url="https://www.booking.com/searchresults.html",
        active_target_id="active",
    )


def test_price_prompt_preserves_read_only_and_explicit_evidence_boundaries() -> None:
    broker = InMemorySessionLeaseBroker()
    task = _price_agent_task(_request(broker))

    assert "Never sign in" in task
    assert "Never infer missing facts" in task
    assert "all-in total for the whole stay" in task
    assert "submit_price_observation" in task


def test_guard_accepts_the_code_owned_search_url_but_not_transaction_checkout() -> None:
    broker = InMemorySessionLeaseBroker()
    trusted_url = build_trusted_search_url(_request(broker))

    assert BrowserUseActionGuard.observable_url_rejection_reason(trusted_url) is None
    assert not BrowserUseActionGuard.observable_url(
        "https://www.booking.com/searchresults.html?action=checkout"
    )


def test_price_entry_prefers_canonical_property_url_with_trusted_query() -> None:
    broker = InMemorySessionLeaseBroker()
    request = _request(broker)
    request = PriceExecutionRequest(
        execution_id=request.execution_id,
        owner_user_id=request.owner_user_id,
        booking_id=request.booking_id,
        query=TrustedPriceQuery(
            property_name=request.query.property_name,
            property_reference="https://www.booking.com/hotel/us/example.html?old=tracking#top",
            stay_dates=request.query.stay_dates,
            occupancy=request.query.occupancy,
            currency=request.query.currency,
        ),
        session_lease=request.session_lease,
        limits=request.limits,
    )

    url, kind = _price_entry_url(request)

    assert kind == "property"
    assert url.startswith("https://www.booking.com/hotel/us/example.html?")
    assert "checkin=2026-11-24" in url
    assert "checkout=2026-11-25" in url
    assert "old=tracking" not in url
    assert "#" not in url


def test_price_entry_uses_search_for_name_only_reference() -> None:
    broker = InMemorySessionLeaseBroker()
    url, kind = _price_entry_url(_request(broker))

    assert kind == "search"
    assert url.startswith("https://www.booking.com/searchresults.html?")


def test_terminal_submission_cannot_claim_observed() -> None:
    try:
        _terminal_status("observed")
    except ValueError as exc:
        assert "cannot claim" in str(exc)
    else:
        raise AssertionError("observed terminal must be rejected")


def test_executor_restores_session_and_returns_redacted_observation() -> None:
    broker = InMemorySessionLeaseBroker()
    request = _request(broker)
    runtime = _Runtime(
        BrowserUsePriceRuntimeResult(
            PriceExecutionStatus.OBSERVED,
            observation=_observation(),
            refreshed_session=b'[{"name":"fresh","value":"secret","domain":".booking.com"}]',
        )
    )
    with AsyncLoopRunner() as runner:
        result = BrowserUsePriceBrowserExecutor(
            api_key="test-key",
            lease_broker=broker,
            budget=_budget(),
            runner=runner,
            runtime_factory=lambda: runtime,
        ).execute(request)

    assert result.status is PriceExecutionStatus.OBSERVED
    assert result.provenance is not None
    assert result.provenance.source is ObservationSource.BROWSER_USE_PRICE_SUBMISSION
    assert result.refreshed_session_eligible is True
    assert runtime.restored is not None and b"secret" in runtime.restored
    assert runtime.closed is True
    assert broker.take_verified_refresh(request.session_lease) is not None
    assert "secret" not in repr(result)


def test_executor_preserves_closed_unsafe_terminal() -> None:
    broker = InMemorySessionLeaseBroker()
    request = _request(broker)
    runtime = _Runtime(
        BrowserUsePriceRuntimeResult(
            PriceExecutionStatus.UNSAFE_ACTION,
            safety_violations=frozenset(
                {ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION}
            ),
        )
    )
    with AsyncLoopRunner() as runner:
        result = BrowserUsePriceBrowserExecutor(
            api_key="test-key",
            lease_broker=broker,
            budget=_budget(),
            runner=runner,
            runtime_factory=lambda: runtime,
        ).execute(request)

    assert result.status is PriceExecutionStatus.UNSAFE_ACTION
    assert result.safety_violations == frozenset(
        {ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION}
    )
    assert result.query_facts is None
    assert runtime.closed is True
