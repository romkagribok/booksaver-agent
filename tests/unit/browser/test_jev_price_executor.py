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
    _state, questions, prices = rate_questions("Standard King Room", room, FLEXIBLE)
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
    _state, questions, prices = rate_questions("Standard King Room", room, FLEXIBLE)
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
    _state, questions, prices = rate_questions("Standard King Room", room, rate)
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
