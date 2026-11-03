"""Shapes from the owner's dad's real confirmation pages (2026-11-03), names replaced."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any

import pytest

from booksaver.infrastructure.browser.jev_price_executor import JevArmMeter
from booksaver.infrastructure.browser.jev_reservation_facts import (
    JevReservationFacts,
    prove_refund,
    prove_total,
    refund_options,
    total_options,
)
from booksaver.infrastructure.llm.typesafe_client import (
    ChoiceAnswer,
    SystemOneResult,
    TypeSafeError,
)

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)

# Euro breakdown, an "approx." line, the dollar total, then the final-price sentence.
CONVERTED = [
    "Cancellation deadlines are in the property's local time.",
    "1 room € 453",
    "13.95 % TAX € 63",
    "Price",
    "(for 1 guest)",
    "approx. € 516",
    "US$577.42",
    "The final price shown is the amount you'll pay to the property.",
    "Your card issuer may charge you a foreign transaction fee.",
    "Payment Info",
]
# One guest, a city tax row, and no final-price sentence.
SINGLE_GUEST = [
    "1 room € 89.29",
    "12 % VAT € 10.71",
    "€ 2 City tax per person per night € 2",
    "Price",
    "(for 1 guest)",
    "€ 102",
    "Additional Info",
    "Note that additional supplements (e.g. an extra bed) aren't added in this total.",
]
# A page that proves two different refund terms, so only Jev can say which one applies.
CONFLICT = "Free cancellation until January 20, 2027."


PARTIAL_REFUND = (
    "You'll get a full refund if you cancel before 11:59 PM on January 23, 2027. If you cancel "
    "before 12:00 AM on January 24, 2027, you'll get a € 589 refund."
)


def _total(lines: list[str], nights: int = 3) -> list[dict[str, str]]:
    return [
        proof for key in total_options(lines)
        if (proof := prove_total(lines, int(key[1:]), {"adults": "1"}, nights)) is not None
    ]


def test_converted_breakdown_proves_only_the_booked_currency_total() -> None:
    assert _total(CONVERTED) == [
        {"booked_total": "577.42", "currency": "USD", "all_in": "explicit"}
    ]


def test_single_guest_page_with_city_tax_proves_its_total() -> None:
    assert _total(SINGLE_GUEST, nights=1) == [
        {"booked_total": "102", "currency": "EUR", "all_in": "explicit"}
    ]


@pytest.mark.parametrize(
    ("lines", "change"),
    [
        (CONVERTED, ("1 room € 453", "1 room € 460")),  # rows miss the conversion
        (CONVERTED, ("13.95 % TAX € 63", "13.95 % TAX € 70")),  # tax does not match its rate
        (CONVERTED, ("13.95 % TAX € 63", "Service fee € 63")),  # an unrecognized row
        (SINGLE_GUEST, ("12 % VAT € 10.71\n", "")),  # no tax row proves taxes are included
        (SINGLE_GUEST, ("€ 102", "€ 103")),  # exact rows, so no rounding is allowed
        (CONVERTED, ("Payment Info", "City tax is not included in your total.")),
        (CONVERTED, ("(for 1 guest)", "(for 1 guest) US$190 per night")),  # second amount
        (SINGLE_GUEST, ("Additional Info", "Additional Info\nMandatory cleaning fee € 25")),
    ],
)
def test_anything_the_page_does_not_prove_stays_unknown(
    lines: list[str], change: tuple[str, str],
) -> None:
    text = "\n".join(lines)
    assert change[0] in text
    changed = [line for line in text.replace(*change).split("\n") if line]
    assert _total(changed, nights=1 if lines is SINGLE_GUEST else 3) == []


def test_refund_proof_takes_the_dated_full_refund_sentence() -> None:
    options = refund_options([PARTIAL_REFUND])
    proven = [p for s in options.values() if (p := prove_refund(s, date(2027, 1, 27), NOW))]
    assert proven == [{
        "refundability": "explicit_refundable",
        "refundability_text": options["r0"],
        "refund_deadline": "2027-01-23",
    }]


def test_explicit_no_refund_wording_is_non_refundable() -> None:
    proof = prove_refund(
        "You won't be eligible for a refund if you cancel this booking.", date(2026, 11, 10), NOW,
    )
    assert proof is not None
    assert proof["refundability"] == "explicit_nonrefundable"


@pytest.mark.parametrize(
    "sentence",
    [
        "Free cancellation available",  # no date
        "Free cancellation within: 8 days 4 hours",
        # After check-in, then in the past.
        "You'll get a full refund if you cancel before 11:59 PM on February 3, 2027.",
        "You'll get a full refund if you cancel before 11:59 PM on October 1, 2026.",
        "Full refund before January 20, 2027 or January 22, 2027.",  # two dates
    ],
)
def test_unproven_refund_sentences_stay_unknown(sentence: str) -> None:
    assert prove_refund(sentence, date(2027, 1, 27), NOW) is None


@pytest.mark.parametrize(
    ("sentence", "proven"),
    [
        ("Free cancellation until 12:00 AM on November 3, 2026.", False),  # today
        ("Free cancellation until 11:59 PM on November 4, 2026.", False),  # could be past at +14
        ("Free cancellation until 11:59 PM on November 5, 2026.", True),
    ],
)
def test_a_cutoff_too_close_for_any_timezone_stays_unknown(sentence: str, proven: bool) -> None:
    assert (prove_refund(sentence, date(2026, 11, 10), NOW) is not None) is proven


class _Client:
    def __init__(self, choice: str | None = None, error: bool = False) -> None:
        self.choice, self.error = choice, error
        self.requests: list[tuple[object, dict[str, Any]]] = []

    def system_one(self, state: object, questions: dict[str, Any], *, deadline: float) -> Any:
        self.requests.append((state, questions))
        if self.error:
            raise TypeSafeError("unavailable")
        return SystemOneResult(
            model="jev",
            answers={"refund": ChoiceAnswer(self.choice or "none", 0.9, {})},
            input_tokens=100, output_tokens=5,
        )


def _assistant(client: _Client, cap: int = 10**9) -> JevReservationFacts:
    return JevReservationFacts(
        client=client,  # type: ignore[arg-type]
        meter=JevArmMeter(max_calls=8, max_cost_nano_usd=cap),
        observed_at=datetime(2026, 11, 3, 12, tzinfo=UTC),
    )


_FACTS = {"check_in": "2027-01-27", "check_out": "2027-02-01", "adults": "2"}
_PAGE = "\n".join(["Guest name", "Real Person", "Confirmation number", "4567891234",
                   "Refund schedule", PARTIAL_REFUND, *SINGLE_GUEST])
_CONFLICTING_PAGE = _PAGE.replace(PARTIAL_REFUND, PARTIAL_REFUND + "\n" + CONFLICT)


def _full_refund_key() -> str:
    options = refund_options(["Refund schedule", PARTIAL_REFUND, CONFLICT])
    return next(key for key, text in options.items() if text.startswith("You'll get a full"))


def test_one_proven_refund_answer_needs_no_jev() -> None:
    client = _Client()
    facts, reasons = dict(_FACTS), {"refundability": "refund_schedule_unrecognized"}
    asyncio.run(_assistant(client)(_PAGE, facts, reasons))
    assert facts["refund_deadline"] == "2027-01-23"
    assert client.requests == []


def test_jev_chooses_between_proven_refund_terms_and_sees_only_those_sentences() -> None:
    client = _Client(_full_refund_key())
    facts, reasons = dict(_FACTS), {"refundability": "refund_schedule_unrecognized"}
    assistant = _assistant(client)

    asyncio.run(assistant(_CONFLICTING_PAGE, facts, reasons))

    assert facts["refund_deadline"] == "2027-01-23"
    assert reasons == {}
    assert assistant.filled == {"refundability": 1}
    sent = repr(client.requests)
    assert "Real Person" not in sent and "4567891234" not in sent and "€ 102" not in sent
    assert "€ 589 refund" not in sent  # an unproven sentence is never offered


def test_assistant_proves_totals_without_asking_jev() -> None:
    client = _Client()
    facts = {**_FACTS, "check_out": "2027-01-28", "adults": "1"}
    reasons = {"booked_total": "guest_count_line"}
    asyncio.run(_assistant(client)(_PAGE, facts, reasons))
    assert (facts["booked_total"], facts["currency"]) == ("102", "EUR")
    assert client.requests == []


@pytest.mark.parametrize("client", [_Client("none"), _Client(error=True)])
def test_no_choice_or_an_error_leaves_the_facts_unknown(client: _Client) -> None:
    facts, reasons = dict(_FACTS), {"refundability": "refund_schedule_unrecognized"}
    asyncio.run(_assistant(client)(_CONFLICTING_PAGE, facts, reasons))
    assert "refund_deadline" not in facts
    assert reasons == {"refundability": "refund_schedule_unrecognized"}


def test_an_exhausted_daily_cap_sends_nothing() -> None:
    client = _Client(_full_refund_key())
    facts, reasons = dict(_FACTS), {"refundability": "refund_schedule_unrecognized"}
    asyncio.run(_assistant(client, cap=0)(_CONFLICTING_PAGE, facts, reasons))
    assert client.requests == []
    assert "refund_deadline" not in facts


def test_at_most_eight_pages_ask_jev_in_one_sync() -> None:
    client = _Client("none")
    assistant = _assistant(client)
    for _ in range(10):
        asyncio.run(assistant(_CONFLICTING_PAGE, dict(_FACTS), {"refundability": "x"}))
    assert len(client.requests) == 8
