from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from booksaver.application.browser_executor import ExecutionMeter
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionLimits,
    ObservationSource,
    PriceExecutionRequest,
    PriceExecutionResult,
    PriceExecutionStatus,
    RedactedProvenance,
    RefundabilityEvidence,
    SessionLeaseReference,
    TrustedPriceQuery,
    validate_price_observation,
)
from booksaver.domain.model_policy import UsdAmount
from booksaver.domain.price_comparison import CostCertainty
from booksaver.domain.value_objects import Occupancy, StayDates
from booksaver.infrastructure.browser.jev_page_snapshot import (
    RoomSnapshot,
    parse_offer_snapshot,
)
from booksaver.infrastructure.browser.jev_price_executor import (
    JevArmMeter,
    JevBudgetStop,
    LocalJevPriceRuntime,
    MeteredJevDecider,
    ground_rate,
    parse_money,
    rate_questions,
)
from booksaver.infrastructure.llm.typesafe_client import (
    ChoiceAnswer,
    SystemOneResult,
    TypeSafeError,
)

PROPERTY = "Hotel Test Downtown"
URL = (
    "https://www.booking.com/hotel/us/hotel-test.html?label=x&checkin=2026-11-24"
    "&checkout=2026-11-25&group_adults=2&group_children=0&no_rooms=1"
)
ROOM_LINES = (
    "Standard King Room", "Bed:", "1 king bed", "220 feet²", "Free Wifi",
    "Included:", "All taxes and charges.",
)
FLEXIBLE = (
    "Flexible", "Price for:", "Max. people: 2", "Free cancellation",
    "before November 22, 2026", "No prepayment needed", "$319", "per night", "$319",
    "Price $319", "1 night", "Reserve",
)
SAVER = (
    "Saver", "Price for:", "Max. people: 2", "Non-refundable", "Pay online", "$287",
    "per night", "$287", "Price $287", "Reserve",
)


def _request() -> PriceExecutionRequest:
    deadline = datetime.now(UTC) + timedelta(minutes=2)
    return PriceExecutionRequest(
        execution_id="jev-test-1",
        owner_user_id=1,
        booking_id="booking-1",
        query=TrustedPriceQuery(
            property_name=PROPERTY,
            property_reference="https://www.booking.com/hotel/us/hotel-test.en-us.html",
            stay_dates=StayDates(date(2026, 11, 24), date(2026, 11, 25)),
            occupancy=Occupancy(adults=2),
            currency="USD",
        ),
        session_lease=SessionLeaseReference(
            lease_id="lease-1",
            owner_user_id=1,
            subject_id="booking-1",
            execution_id="jev-test-1",
            expires_at=deadline,
        ),
        limits=ExecutionLimits(deadline=deadline, max_computer_use_actions=0),
    )


def _choice(options: Mapping[str, object], chosen: str) -> ChoiceAnswer:
    probabilities = {key: (1.0 if key == chosen else 0.0) for key in options}
    return ChoiceAnswer(chosen, 1.0, probabilities)


def _option(options: Mapping[str, object], predicate: Any) -> str:
    return next(key for key, value in options.items() if predicate(str(value)))


class ScriptedJev:
    """Answer like a sensible Jev would, from the offered options only."""

    def __init__(self, *, taxes: str = "included", fail_on: str | None = None) -> None:
        self.taxes = taxes
        self.fail_on = fail_on
        self.states: list[object] = []

    async def ask(
        self, state: object, questions: Mapping[str, Mapping[str, object]]
    ) -> SystemOneResult:
        self.states.append(state)
        if self.fail_on in questions:
            raise TypeSafeError("unavailable")
        answers: dict[str, ChoiceAnswer] = {}
        for question_id, question in questions.items():
            options: Mapping[str, object] = question["criteria"]  # type: ignore[assignment]
            if question_id == "property":
                chosen = _option(options, lambda v: v == PROPERTY)
            elif question_id == "room_name":
                chosen = "l0"
            elif question_id == "total":
                chosen = _option(options, lambda v: v.startswith("Price $"))
            elif question_id == "refund":
                lines = state["rate_option_lines"]  # type: ignore[index]
                chosen = (
                    "free_cancellation" if "Free cancellation" in lines else "non_refundable"
                )
            elif question_id == "refund_line":
                chosen = _option(
                    options, lambda v: "cancellation" in v.lower() or "refundable" in v.lower()
                )
            elif question_id == "taxes":
                chosen = self.taxes
            else:  # pragma: no cover - unexpected question
                raise AssertionError(question_id)
            answers[question_id] = _choice(options, chosen)
        return SystemOneResult(model="jev-1.13.0", answers=answers, input_tokens=300,
                               output_tokens=5)


def _snapshot(room_lines: tuple[str, ...] = ROOM_LINES) -> Any:
    return parse_offer_snapshot(
        {
            "url": URL,
            "title": f"{PROPERTY}, West Lafayette – Updated 2026 Prices",
            "headings": ["Booking.com", PROPERTY, "Reviews", "Standard King Room"],
            "viewport_text": "",
            "rooms": [{"lines": list(room_lines), "rates": [list(SAVER), list(FLEXIBLE)]}],
        }
    )


def _extract(jev: ScriptedJev, snapshot: Any = None) -> Any:
    runtime = LocalJevPriceRuntime()
    return asyncio.run(runtime._extract(_request(), snapshot or _snapshot(), jev))


def test_parse_money_is_exact_and_fails_closed_on_ambiguity() -> None:
    assert parse_money("Price $1,319.50", "USD") == parse_money("US$1,319.50", "USD")
    assert parse_money("€ 94", "EUR").amount == Decimal("94")  # type: ignore[union-attr]
    assert parse_money("CA$410", "CAD").currency == "CAD"  # type: ignore[union-attr]
    assert parse_money("$410", "CAD") is None  # bare dollar is USD-only
    assert parse_money("$287 $319", "USD") is None
    assert parse_money("Max. people: 2", "USD") is None


def test_extraction_returns_validated_whole_stay_offers() -> None:
    observation = _extract(ScriptedJev())

    facts = observation.facts
    assert facts.property_name == PROPERTY
    assert facts.property_reference == "https://www.booking.com/hotel/us/hotel-test.html"
    assert (facts.check_in, facts.check_out) == (date(2026, 11, 24), date(2026, 11, 25))
    assert facts.occupancy == Occupancy(adults=2) and facts.currency == "USD"
    assert facts.completeness is EvidenceCompleteness.COMPLETE
    saver, flexible = observation.offers
    assert flexible.total.amount == Decimal("319")
    assert flexible.refundability is RefundabilityEvidence.EXPLICIT_REFUNDABLE
    assert flexible.refundability_text == "Free cancellation before November 22, 2026"
    assert flexible.all_in is AllInEvidence.EXPLICIT
    assert saver.refundability is RefundabilityEvidence.EXPLICIT_NONREFUNDABLE

    request = _request()
    result = PriceExecutionResult(
        PriceExecutionStatus.OBSERVED,
        query_facts=facts,
        offers=observation.offers,
        provenance=RedactedProvenance(
            source=ObservationSource.JEV_PRICE_SUBMISSION,
            action_count=1,
            evidence_item_count=observation.evidence_item_count,
        ),
    )
    validation = validate_price_observation(request, result)
    assert validation.accepted
    assert [offer.total.amount for offer in validation.accepted_offers] == [Decimal("319")]


def test_taxes_excluded_text_keeps_offers_out_of_all_in_comparison() -> None:
    excluded_room = (*ROOM_LINES[:5], "Not included:", "12 % TAX.")
    observation = _extract(ScriptedJev(taxes="included"), _snapshot(excluded_room))
    # Jev claimed "included" but the card says otherwise: conflicting, never explicit.
    assert {offer.all_in for offer in observation.offers} == {AllInEvidence.CONFLICTING}
    observation = _extract(ScriptedJev(taxes="excluded"), _snapshot(excluded_room))
    assert {offer.all_in for offer in observation.offers} == {AllInEvidence.UNKNOWN}


def test_per_night_choice_and_unsupported_refund_claim_are_not_grounded() -> None:
    room = RoomSnapshot(ROOM_LINES, (FLEXIBLE,))
    _state, questions, prices = rate_questions("Standard King Room", room, FLEXIBLE, nights=1)
    per_night = _option(prices, lambda v: v.startswith("$319 (followed by: per night"))
    answers = {
        "total": _choice(questions["total"]["criteria"], per_night),  # type: ignore[arg-type]
        "refund": _choice(questions["refund"]["criteria"], "free_cancellation"),  # type: ignore[arg-type]
        # Jev points at a line that does not state a cancellation policy.
        "refund_line": _choice(questions["refund_line"]["criteria"], "l0"),  # type: ignore[arg-type]
        "taxes": _choice(questions["taxes"]["criteria"], "included"),  # type: ignore[arg-type]
    }
    result = SystemOneResult("jev-1.13.0", answers, 10, 0)
    evidence = ground_rate(result, room, FLEXIBLE, prices, expected_currency="USD", nights=1)
    assert evidence.total is None and not evidence.complete
    assert evidence.refundability == "conflicting"


def test_stated_nights_must_match_the_requested_stay() -> None:
    room = RoomSnapshot(ROOM_LINES, (FLEXIBLE,))
    _state, questions, prices = rate_questions("Standard King Room", room, FLEXIBLE, nights=1)
    total = _option(prices, lambda v: v.startswith("Price $"))
    answers = {
        "total": _choice(questions["total"]["criteria"], total),  # type: ignore[arg-type]
        "refund": _choice(questions["refund"]["criteria"], "not_stated"),  # type: ignore[arg-type]
        "refund_line": _choice(questions["refund_line"]["criteria"], "none"),  # type: ignore[arg-type]
        "taxes": _choice(questions["taxes"]["criteria"], "not_stated"),  # type: ignore[arg-type]
    }
    result = SystemOneResult("jev-1.13.0", answers, 10, 0)
    evidence = ground_rate(result, room, FLEXIBLE, prices, expected_currency="USD", nights=3)
    assert evidence.total is not None and not evidence.complete


def test_missing_url_stay_facts_mark_the_query_incomplete() -> None:
    snapshot = parse_offer_snapshot(
        {
            "url": "https://www.booking.com/hotel/us/hotel-test.html",
            "title": PROPERTY,
            "headings": [PROPERTY],
            "rooms": [{"lines": list(ROOM_LINES), "rates": [list(FLEXIBLE)]}],
        }
    )
    observation = _extract(ScriptedJev(), snapshot)
    assert observation.facts.completeness is EvidenceCompleteness.INCOMPLETE


def test_page_state_is_bounded_and_carries_no_session_material() -> None:
    jev = ScriptedJev()
    _extract(jev)
    serialized = repr(jev.states)
    assert "cookie" not in serialized.casefold() and "lease" not in serialized.casefold()
    assert len(jev.states) == 1 + 1 + 2  # property, room name, one call per rate


def test_provider_failure_propagates() -> None:
    with pytest.raises(TypeSafeError):
        _extract(ScriptedJev(fail_on="room_name"))


def test_meter_charges_exact_usage_and_conservative_unresolved_attempts() -> None:
    meter = JevArmMeter(max_calls=2, max_cost_nano_usd=10**9)
    limits = ExecutionLimits(
        deadline=datetime.now(UTC) + timedelta(minutes=1), max_job_cost=UsdAmount(1_000)
    )
    execution = ExecutionMeter(limits)

    class Client:
        def __init__(self) -> None:
            self.calls = 0

        def system_one(self, *_args: Any, **_kwargs: Any) -> SystemOneResult:
            self.calls += 1
            if self.calls == 1:
                return SystemOneResult("jev-1.13.0", {}, 1_000, 3, unresolved_attempts=1,
                                       estimated_input_tokens=500)
            raise TypeSafeError("unavailable", unresolved_attempts=1, estimated_input_tokens=200)

    decider = MeteredJevDecider(Client(), meter, execution, deadline=10**12)  # type: ignore[arg-type]
    asyncio.run(decider.ask("s", {}))
    with pytest.raises(TypeSafeError):
        asyncio.run(decider.ask("s", {}))
    with pytest.raises(JevBudgetStop):
        asyncio.run(decider.ask("s", {}))

    usage = meter.snapshot()
    assert usage.calls == 2 and usage.input_tokens == 1_000
    assert usage.cost_nano_usd == (1_000 + 500 + 200) * 42
    assert usage.certainty is CostCertainty.CONSERVATIVE
    snapshot = execution.snapshot()
    assert snapshot.model_calls == 2 and snapshot.cost.micro_usd == 63 + 9


def test_requests_cut_off_by_the_deadline_are_charged_conservatively() -> None:
    meter = JevArmMeter(max_calls=5, max_cost_nano_usd=10**9)
    meter.admit()
    meter.record(SystemOneResult("jev-1.13.0", {}, 6_000, 0))
    meter.admit()  # still in flight when the arm times out
    meter.abandon_in_flight()
    usage = meter.snapshot()
    assert usage.cost_nano_usd == (6_000 + 6_000) * 42
    assert usage.certainty is CostCertainty.CONSERVATIVE


@pytest.mark.parametrize(
    "text",
    ["€ 1.234", "1.234 €", "₹1,23,456", "€ 450,50", "$287.5"],
)
def test_non_us_number_grouping_fails_closed(text: str) -> None:
    assert parse_money(text, "EUR" if "€" in text else "INR" if "₹" in text else "USD") is None


def _grounded(rate: tuple[str, ...], *, total_line: str, refund: str, refund_line: str) -> Any:
    room = RoomSnapshot(ROOM_LINES, (rate,))
    _state, questions, prices = rate_questions("Standard King Room", room, rate, nights=1)
    total = _option(prices, lambda v: v.startswith(total_line))
    line = _option(
        questions["refund_line"]["criteria"],  # type: ignore[arg-type]
        lambda v: v == refund_line,
    )
    answers = {
        "total": _choice(questions["total"]["criteria"], total),  # type: ignore[arg-type]
        "refund": _choice(questions["refund"]["criteria"], refund),  # type: ignore[arg-type]
        "refund_line": _choice(questions["refund_line"]["criteria"], line),  # type: ignore[arg-type]
        "taxes": _choice(questions["taxes"]["criteria"], "included"),  # type: ignore[arg-type]
    }
    result = SystemOneResult("jev-1.13.0", answers, 10, 0)
    return ground_rate(result, room, rate, prices, expected_currency="USD", nights=1)


@pytest.mark.parametrize("line", ["+$45 taxes and charges", "Deposit: $100", "From $99"])
def test_component_or_teaser_amounts_are_never_a_total(line: str) -> None:
    rate = ("Flexible", "Free cancellation", line, "Price $319")
    evidence = _grounded(rate, total_line=line, refund="free_cancellation",
                         refund_line="Free cancellation")
    assert evidence.total is None and not evidence.complete


@pytest.mark.parametrize("policy", ["Partially refundable", "No free cancellation"])
def test_partial_refund_terms_are_never_grounded_as_refundable(policy: str) -> None:
    rate = ("Flexible", policy, "Price $319")
    evidence = _grounded(rate, total_line="Price $319", refund="free_cancellation",
                         refund_line=policy)
    assert evidence.refundability == "conflicting"


def test_total_question_states_the_stay_length_and_booking_label() -> None:
    room = RoomSnapshot(ROOM_LINES, (FLEXIBLE,))
    state, questions, _prices = rate_questions("Standard King Room", room, FLEXIBLE, nights=1)
    instructions = questions["total"]["instructions"]
    assert state["stay_nights"] == 1
    assert "stay of 1 night." in instructions["question"]  # type: ignore[index]
    assert "Price $X" in instructions["hint"]  # type: ignore[index]
    _state, plural, _prices = rate_questions("Standard King Room", room, FLEXIBLE, nights=3)
    assert "stay of 3 nights." in plural["total"]["instructions"]["question"]  # type: ignore[index]


# --- diagnostics: a failed run must explain itself without storing page content ------------


class _NavJev:
    """Scripted navigation decisions; records the offered operations."""

    def __init__(self, *operations: str) -> None:
        self.operations = list(operations)
        self.asked = 0

    async def ask(
        self, _state: object, questions: Mapping[str, Mapping[str, object]]
    ) -> SystemOneResult:
        self.asked += 1
        options: Mapping[str, object] = questions["operation"]["criteria"]  # type: ignore[assignment]
        chosen = self.operations.pop(0) if self.operations else "WAIT"
        return SystemOneResult(
            "jev-1.13.0", {"operation": _choice(options, chosen)}, 600, 0
        )


class _NavSession:
    agent_focus_target_id = "target-1"

    def __init__(self) -> None:
        self.event_bus = self
        self.scrolls = 0

    def get_page_targets(self) -> list[object]:
        return [object()]

    async def get_current_page_url(self) -> str:
        return URL

    async def get_browser_state_summary(self, **_kwargs: Any) -> Any:
        raise RuntimeError("no interactive state in this fixture")

    def dispatch(self, _event: object) -> Any:
        self.scrolls += 1

        class Done:
            def __await__(self) -> Any:
                return iter(())

            async def event_result(self, **_kwargs: Any) -> None:
                return None

        return Done()


OOPS_TEXT = "Oops! Something went wrong on our side. Reference 8F2K-PRIVATE-TOKEN"


def _oops_snapshot() -> Any:
    return parse_offer_snapshot(
        {
            "url": URL + "&chal_t=1790524727227",
            "title": "Booking.com",
            "headings": ["Oops!"],
            "viewport_text": OOPS_TEXT,
            "rooms": [],
        }
    )


def _navigate(runtime: LocalJevPriceRuntime, jev: _NavJev, snapshot: Any) -> Any:
    async def no_wait(_session: Any, *, seconds: float = 0.0) -> Any:
        return snapshot

    runtime._await_offers = no_wait  # type: ignore[method-assign]
    meter = ExecutionMeter(_request().limits)
    return asyncio.run(
        runtime._navigate_until_offers(
            _request(), _NavSession(), {"width": 412, "height": 915}, jev, meter
        )
    )


def test_page_signature_reports_categories_never_content() -> None:
    from booksaver.infrastructure.browser.jev_price_executor import page_signature

    assert page_signature(None, PROPERTY) == "nosnap"
    assert page_signature(_snapshot(), PROPERTY) == "property r1 h4 t0 name"
    signature = page_signature(_oops_snapshot(), PROPERTY)
    assert signature == f"property r0 h1 t{len(OOPS_TEXT)} oops+chal"
    assert "PRIVATE" not in signature and "wrong" not in signature


def test_exhausted_navigation_explains_what_it_saw_and_chose() -> None:
    runtime = LocalJevPriceRuntime()
    jev = _NavJev("WAIT", "SCROLL_DOWN", "WAIT", "WAIT", "SCROLL_DOWN", "WAIT")
    status = _navigate(runtime, jev, _oops_snapshot())

    assert status is PriceExecutionStatus.NO_VALID_OBSERVATION and jev.asked == 6
    diagnostic = runtime.diagnostic
    page = f"property r0 h1 t{len(OOPS_TEXT)} oops+chal"
    assert f"nav=[{page} c0>WAIT@1.00 | {page} c0>SCROLL@1.00 | " in diagnostic
    assert diagnostic.count(">WAIT@") == 4 and diagnostic.count(">SCROLL@") == 2
    assert f"end=no_rooms_after_6_decisions({page})" in diagnostic
    assert "ready=0s" in diagnostic
    # Categories and counts only: no page text, URL, or property name.
    for private in ("PRIVATE", "Something went wrong", "booking.com", PROPERTY, "chal_t="):
        assert private not in diagnostic
    assert len(diagnostic) <= 400


def test_jev_declaring_itself_blocked_is_recorded_as_such() -> None:
    runtime = LocalJevPriceRuntime()
    status = _navigate(runtime, _NavJev("WAIT", "BLOCKED"), None)
    assert status is PriceExecutionStatus.NO_VALID_OBSERVATION
    assert "nav=[nosnap c0>WAIT@1.00 | nosnap c0>BLOCKED@1.00] end=jev_blocked" in (
        runtime.diagnostic
    )


def test_rooms_already_present_needs_no_navigation_decision() -> None:
    runtime = LocalJevPriceRuntime()
    jev = _NavJev()
    snapshot = _navigate(runtime, jev, _snapshot())
    assert snapshot.rooms and jev.asked == 0
    assert "end=rooms_found" in runtime.diagnostic and "nav=[" not in runtime.diagnostic


def test_extraction_records_how_far_each_offer_got() -> None:
    runtime = LocalJevPriceRuntime()
    asyncio.run(runtime._extract(_request(), _snapshot(), ScriptedJev()))
    assert (
        "rooms=1 rates=2 named=1 asked=2 priced=2 refundable=1 all_in=2 complete=2 "
        "property=y stay_facts=y"
    ) in runtime.diagnostic


class _DiagnosedRuntime:
    diagnostic = "entry=property stage=navigation end=no_rooms_after_6_decisions(other r0 h0 t0)"
    failure_stage = "jev_navigation"

    def __init__(self, *, hang: bool = False) -> None:
        self.hang = hang
        self.closed = False

    def restore_session(self, _data: bytes) -> None:
        return None

    async def execute(self, _request: Any, *, decider: Any, meter: Any) -> Any:
        from booksaver.infrastructure.browser.jev_price_executor import JevPriceRuntimeResult

        if self.hang:
            await asyncio.sleep(30)
        return JevPriceRuntimeResult(PriceExecutionStatus.NO_VALID_OBSERVATION)

    async def close(self) -> None:
        self.closed = True


def _facade_run(runtime: _DiagnosedRuntime, *, timeout_seconds: int) -> Any:
    from booksaver.application.async_runner import AsyncLoopRunner
    from booksaver.application.browser_executor import InMemorySessionLeaseBroker
    from booksaver.infrastructure.browser.jev_price_executor import JevPriceBrowserExecutor

    broker = InMemorySessionLeaseBroker()
    lease = broker.issue(
        owner_user_id=1, execution_id="jev-test-1", session_material=b"[]", subject_id="booking-1"
    )
    base = _request()
    request = PriceExecutionRequest(
        execution_id=base.execution_id,
        owner_user_id=base.owner_user_id,
        booking_id=base.booking_id,
        query=base.query,
        session_lease=lease,
        limits=ExecutionLimits(
            deadline=datetime.now(UTC) + timedelta(seconds=60),
            max_computer_use_actions=0,
            timeout_seconds=timeout_seconds,
        ),
    )
    with AsyncLoopRunner() as runner:
        executor = JevPriceBrowserExecutor(
            client=object(),  # type: ignore[arg-type]
            lease_broker=broker,
            runner=runner,
            max_calls=10,
            max_cost_nano_usd=10**9,
            runtime_factory=lambda: runtime,  # type: ignore[arg-type,return-value]
        )
        return executor, executor.execute(request)


def test_unobserved_run_keeps_and_logs_its_diagnostic(caplog: pytest.LogCaptureFixture) -> None:
    runtime = _DiagnosedRuntime()
    with caplog.at_level("WARNING"):
        executor, result = _facade_run(runtime, timeout_seconds=20)
    assert result.status is PriceExecutionStatus.NO_VALID_OBSERVATION and runtime.closed
    assert executor.last_diagnostic == runtime.diagnostic
    [record] = [r for r in caplog.records if "Jev price not observed" in r.getMessage()]
    assert "status=no_valid_observation" in record.getMessage()
    assert "end=no_rooms_after_6_decisions" in record.getMessage()


def test_timed_out_run_still_reports_where_it_was(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        executor, result = _facade_run(_DiagnosedRuntime(hang=True), timeout_seconds=1)
    assert result.status is PriceExecutionStatus.TIMEOUT
    assert "stage=navigation" in executor.last_diagnostic
    assert any("status=timeout" in r.getMessage() for r in caplog.records)
