from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from booksaver.application.async_runner import AsyncLoopRunner
from booksaver.application.browser_executor import ExecutionMeter, InMemorySessionLeaseBroker
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
    PriceExecutionResult,
    PriceExecutionStatus,
    RedactedProvenance,
    RefundabilityEvidence,
    TrustedPriceQuery,
    validate_price_observation,
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
from booksaver.infrastructure.browser import browser_use_price_executor as price_adapter
from booksaver.infrastructure.browser.agentic_executor import (
    TypedObservation,
    build_trusted_search_url,
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
from booksaver.infrastructure.browser.browser_use_runtime import (
    BrowserUseActionGuard,
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
        subject_id="booking-1",
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


def test_terminal_schema_and_prompt_enumerate_only_existing_failure_statuses() -> None:
    expected = {
        status.value for status in PriceExecutionStatus
        if status is not PriceExecutionStatus.OBSERVED
    }
    schema = BrowserUsePriceTerminalSubmission.model_json_schema()
    assert set(schema["properties"]["status"]["enum"]) == expected
    assert len(expected) == 11
    prompt = _price_agent_task(_request(InMemorySessionLeaseBroker()))
    for status in expected:
        assert status in prompt
        assert _terminal_status(status).value == status
        assert BrowserUsePriceTerminalSubmission(success=False, status=status).status == status
    assert "Use no_valid_observation for missing or ambiguous query evidence" in prompt
    assert "BookSaver filters each offer and decides equivalence" in prompt


@pytest.mark.parametrize("status", [
    "observed", "no_equivalent_offer", "incomplete_evidence", "secret",
])
def test_terminal_schema_rejects_observation_and_invented_reasons(status) -> None:
    with pytest.raises(ValidationError):
        BrowserUsePriceTerminalSubmission(success=False, status=status)


def _local_price_episode(monkeypatch, tmp_path, plan):
    """Use real registered handlers with no browser, model, or network calls."""
    import browser_use

    class Tools:
        def __init__(self, **kwargs):
            self.registry = SimpleNamespace(registry=SimpleNamespace(actions={}))
            self.descriptions = {}

        def action(self, description, **kwargs):
            def register(function):
                self.registry.registry.actions[function.__name__] = function
                self.descriptions[function.__name__] = description
                return function
            return register

    class Session:
        url = "https://www.booking.com/searchresults.html"

        async def navigate_to(self, url, **kwargs):
            self.url = url

        async def get_current_page_url(self):
            return self.url

        def get_page_targets(self):
            return [object()]

        async def get_browser_state_summary(self, **kwargs):
            return SimpleNamespace(
                dom_state=SimpleNamespace(llm_representation=lambda: "secret DOM"),
            )

    runtime = price_adapter.LocalBrowserUsePriceRuntime()
    session = Session()
    request = _request(InMemorySessionLeaseBroker())
    meter = ExecutionMeter(request.limits)

    async def start():
        return SimpleNamespace(
            browser=session, viewport={"width": 360, "height": 800}, file_system_dir=tmp_path,
        )

    async def verify(*args):
        return None

    async def screenshot(*args):
        return True

    def create_agent(agent_type, **kwargs):
        agent = SimpleNamespace(history=SimpleNamespace(history=[]))

        async def run(**run_kwargs):
            await plan(agent, kwargs["tools"], session)
            return agent.history
        agent.run = run
        return agent

    monkeypatch.setattr(browser_use, "Tools", Tools)
    monkeypatch.setattr(
        price_adapter, "budgeted_model_type", lambda *args: lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(price_adapter, "browser_use_screenshot_available", screenshot)
    monkeypatch.setattr(runtime, "_host", SimpleNamespace(
        start=start, verify_authentication=verify, create_agent=create_agent,
        dialog_rejected=False, blocked_network_requests=0, blocked_network_hosts=set(),
    ))
    return runtime, runtime.execute(request, api_key="secret key", budget=_budget(), meter=meter)


@pytest.mark.parametrize("invalid", ["invented_reason", "observed"])
def test_terminal_correction_lists_choices_then_accepts_valid_failure(
    monkeypatch, tmp_path, invalid,
):
    async def plan(agent, tools, session):
        done = tools.registry.registry.actions["done"]
        # Exercise defensive handler validation even if a dependency bypasses the typed schema.
        rejected = await done(SimpleNamespace(success=False, status=invalid), session)
        assert rejected.is_done is False
        assert rejected.success is None
        for status in PriceExecutionStatus:
            if status is not PriceExecutionStatus.OBSERVED:
                assert status.value in rejected.extracted_content
                assert status.value in tools.descriptions["done"]
        accepted = await done(BrowserUsePriceTerminalSubmission(
            success=False, status="no_valid_observation"), session)
        assert accepted.is_done is True
        assert accepted.success is False

    runtime, episode = _local_price_episode(monkeypatch, tmp_path, plan)
    result = asyncio.run(episode)
    assert result.status is PriceExecutionStatus.NO_VALID_OBSERVATION
    assert result.observation is None
    assert runtime._price_state.observation is None


def test_successful_done_still_requires_typed_observation(monkeypatch, tmp_path):
    async def plan(agent, tools, session):
        result = await tools.registry.registry.actions["done"](BrowserUsePriceTerminalSubmission(
            success=True, status="no_valid_observation"), session)
        assert result.is_done is False
        assert "submit_price_observation" in result.extracted_content

    runtime, episode = _local_price_episode(monkeypatch, tmp_path, plan)
    result = asyncio.run(episode)
    assert result.status is PriceExecutionStatus.PROVIDER_FAILURE
    assert result.observation is None
    assert runtime._price_state.terminal is None


@pytest.mark.parametrize("broken_history", [False, True])
def test_cancelled_price_run_logs_only_bounded_partial_history_and_reraises(
    monkeypatch, tmp_path, caplog, broken_history,
):
    started = asyncio.Event()

    class Action:
        def model_dump(self, **kwargs):
            if broken_history:
                raise RuntimeError("secret action payload")
            return {"done": {"status": "secret model value", "success": False}}

    async def plan(agent, tools, session):
        agent.history.history.append(SimpleNamespace(
            model_output=SimpleNamespace(action=[Action()]),
            result=[SimpleNamespace(error="validation done status literal_error secret error")],
            state=SimpleNamespace(url="https://www.booking.com/?auth_key=secret-cookie"),
        ))
        started.set()
        await asyncio.Event().wait()

    runtime, episode = _local_price_episode(monkeypatch, tmp_path, plan)

    async def cancel():
        task = asyncio.create_task(episode)
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())
    assert "outcome=cancelled" in caplog.text
    assert "steps=1" in caplog.text
    expected_action = "invalid_action" if broken_history else "done"
    assert f"actions=('{expected_action}',)" in caplog.text
    assert "validation:done:status:literal_error" in caplog.text
    assert "model_calls=0 total_actions=1" in caplog.text
    assert "observation_submitted=False" in caplog.text
    assert "secret" not in caplog.text
    assert "auth_key" not in caplog.text
    assert runtime._price_state.observation is None


def _mixed_price_submission(*, completeness="complete"):
    valid = BrowserUsePriceOfferSubmission(
        room_label="Deluxe King Room", total="275.00", currency="USD", all_in="explicit",
        refundability="explicit_refundable", refundability_text="Free cancellation",
        completeness="complete",
    )
    return BrowserUsePriceObservationSubmission(
        property_name="Hotel Example", check_in="2026-11-24", check_out="2026-11-25",
        adults="2", children="0", rooms="1", currency="USD", genius="unknown",
        completeness=completeness,
        offers=[
            valid,
            valid.model_copy(update={
                "total": "240.00", "all_in": "unknown", "refundability": "unknown",
                "refundability_text": "unknown",
                "completeness": "incomplete",
            }),
            valid.model_copy(update={
                "total": "230.00", "refundability": "explicit_nonrefundable",
                "refundability_text": "Non-refundable",
            }),
            valid.model_copy(update={"total": "220.00", "completeness": "conflicting"}),
        ],
    )


def test_complete_query_with_mixed_offers_keeps_only_valid_candidate(monkeypatch, tmp_path):
    submission = _mixed_price_submission()
    property_url = "https://www.booking.com/hotel/us/example.html"

    async def plan(agent, tools, session):
        session.url = property_url
        submitted = await tools.registry.registry.actions["submit_price_observation"](
            submission, session,
        )
        assert submitted.is_done is True
        assert submitted.success is True

    runtime, episode = _local_price_episode(monkeypatch, tmp_path, plan)
    result = asyncio.run(episode)
    assert result.status is PriceExecutionStatus.OBSERVED
    observation = result.observation
    assert observation is not None
    assert observation.facts.completeness is EvidenceCompleteness.COMPLETE
    assert observation.facts.genius is None
    assert len(observation.offers) == 4
    assert observation.offers[1].completeness is EvidenceCompleteness.INCOMPLETE
    assert observation.offers[1].all_in is AllInEvidence.UNKNOWN
    assert observation.offers[1].refundability is RefundabilityEvidence.UNKNOWN
    assert observation.offers[1].refundability_text == "unknown"
    assert observation.offers[2].refundability is RefundabilityEvidence.EXPLICIT_NONREFUNDABLE
    assert observation.offers[3].completeness is EvidenceCompleteness.CONFLICTING
    request = _request(InMemorySessionLeaseBroker())
    request = replace(request, query=replace(request.query, property_reference=property_url))
    validation = validate_price_observation(request, PriceExecutionResult(
        status=result.status, query_facts=observation.facts, offers=observation.offers,
        provenance=RedactedProvenance(
            source=ObservationSource.BROWSER_USE_PRICE_SUBMISSION, action_count=1,
            evidence_item_count=observation.evidence_item_count,
        ),
    ))
    assert validation.accepted
    assert validation.rejected_offer_count == 3
    assert len(validation.accepted_offers) == 1
    assert validation.accepted_offers[0].total.amount == Decimal("275.00")
    assert runtime._price_state.offers == submission.offers


@pytest.mark.parametrize("completeness", ["incomplete", "conflicting"])
def test_incomplete_query_still_rejected_with_separate_offer_guidance(
    monkeypatch, tmp_path, completeness,
):
    submission = _mixed_price_submission(completeness=completeness)

    async def plan(agent, tools, session):
        submitted = await tools.registry.registry.actions["submit_price_observation"](
            submission, session,
        )
        assert submitted.is_done is False
        guidance = submitted.extracted_content
        assert "Top-level completeness covers only" in guidance
        assert "Offer completeness, all_in, and refundability are independent" in guidance
        assert "Inspect any missing or conflicting query facts" in guidance
        assert "done(success=false, status=no_valid_observation)" in guidance
        assert "Do not resubmit unchanged evidence or mark missing query facts complete" in guidance
        await tools.registry.registry.actions["done"](BrowserUsePriceTerminalSubmission(
            success=False, status="no_valid_observation"), session)

    runtime, episode = _local_price_episode(monkeypatch, tmp_path, plan)
    result = asyncio.run(episode)
    assert result.status is PriceExecutionStatus.NO_VALID_OBSERVATION
    assert result.observation is None
    assert runtime._price_state.query is None
    assert runtime._price_state.offers == []
    assert submission.completeness == completeness


def test_price_prompt_separates_query_and_offer_completeness():
    prompt = _price_agent_task(_request(InMemorySessionLeaseBroker()))
    assert "top-level completeness describes ONLY the visible query" in prompt
    assert "Each offer has its own independent completeness, all_in, and refundability" in prompt
    assert "some offers are incomplete, unknown, or nonrefundable" in prompt
    assert "Never change a completeness value just to pass validation" in prompt
    assert "use refundability=unknown and refundability_text=unknown" in prompt
    assert "Do not fabricate missing totals" in prompt
    assert "and all currently visible room/rate offers are explicit" not in prompt
