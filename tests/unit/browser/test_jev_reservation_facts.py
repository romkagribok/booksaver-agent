"""Jev reads, code wins where it reads (ADR-060). Shapes from the owner's dad's real pages."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any

import pytest

from booksaver.infrastructure.browser.jev_price_executor import JevArmMeter
from booksaver.infrastructure.browser.jev_reservation_facts import (
    JevReservationFacts,
    cancellation_sentences,
    check_refund,
    check_total,
    price_area,
)
from booksaver.infrastructure.llm.typesafe_client import (
    ChoiceAnswer,
    SystemOneResult,
    TypeSafeError,
)

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)
PAGE = [
    "Guest name", "Real Person", "Confirmation number", "4567891234",
    "Cancellation cost", "Free cancellation within: 4 days 10 hours",
    "until November 7, 2026 11:59 PM: US$0",
    "from November 8, 2026 12:00 AM: US$191.44 – Changing the dates of your stay isn't possible.",
    "1 room € 453", "13.95 % TAX € 63", "Price", "(for 1 guest)", "approx. € 516", "US$577.42",
    "The final price shown is the amount you'll pay to the property.", "Payment Info",
]
TEXT = "\n".join(PAGE)


AREA = price_area(PAGE)
SENTENCES = cancellation_sentences(PAGE)


def test_candidates_are_money_lines_and_cancellation_sentences_without_personal_data() -> None:
    assert "US$577.42" in AREA and "approx. € 516" in AREA
    assert "Free cancellation within: 4 days 10 hours" in SENTENCES
    sent = repr((AREA, SENTENCES))
    assert "Real Person" not in sent and "4567891234" not in sent


def test_a_total_must_be_the_largest_amount_in_its_currency() -> None:
    assert check_total("US$577.42", AREA) == {
        "booked_total": "577.42", "currency": "USD", "all_in": "explicit",
        "booked_total_source": "jev",
    }
    assert check_total("from November 8, 2026 12:00 AM: US$191.44 – Changing", AREA) is None
    assert check_total("1 room € 453", AREA) is None  # a component, not the total
    assert check_total("Price", AREA) is None


@pytest.mark.parametrize(
    ("terms", "sentence", "deadline"),
    [
        ("free_until_date", "Free cancellation within: 4 days 10 hours", "2026-11-07"),
        (
            "free_until_date",
            "You'll get a full refund if you cancel before 11:59 PM on January 23, 2027.",
            "2027-01-23",
        ),
        ("free_until_date", "Free cancellation within: 10 hours", None),  # inside the margin
        ("free_until_date", "Free cancellation until November 3, 2026.", None),  # today
        ("free_until_date", "Free cancellation until March 1, 2027.", None),  # after check-in
        ("free_until_date", "Free cancellation available", None),  # no date
        ("free_until_date", "Full refund before January 20, 2027 or January 22, 2027.", None),
        ("not_stated", "Free cancellation until January 20, 2027.", None),
    ],
)
def test_refund_deadline_is_parsed_by_code_with_a_timezone_margin(
    terms: str, sentence: str, deadline: str | None,
) -> None:
    result = check_refund(terms, sentence, date(2027, 1, 27), NOW)
    assert (result or {}).get("refund_deadline") == deadline


def test_non_refundable_needs_jevs_agreed_class() -> None:
    result = check_refund("non_refundable", "Cancellation policy Non-refundable", None, NOW)
    assert result == {"refundability": "explicit_nonrefundable",
                      "refundability_text": "Cancellation policy Non-refundable"}


class _Client:
    def __init__(self, *runs: dict[str, tuple[str, float]], error: bool = False) -> None:
        self.runs, self.error, self.requests = list(runs), error, []

    def system_one(self, state: object, questions: Any, *, deadline: float) -> Any:
        self.requests.append((state, questions))
        if self.error:
            raise TypeSafeError("unavailable")
        run = self.runs[(len(self.requests) - 1) % len(self.runs)]
        return SystemOneResult(
            model="jev", input_tokens=100, output_tokens=5,
            answers={q: ChoiceAnswer(c, conf, {}) for q, (c, conf) in run.items()},
        )


def _answers(total: str = "US$577.42", terms: str = "free_until_date",
             line: str = "Free cancellation within", conf: float = 0.9) -> dict[str, Any]:
    return {
        "total": (next(f"m{i}" for i, line in enumerate(AREA) if line.startswith(total)), conf),
        "refund": (terms, conf),
        "refund_line": (next(f"r{i}" for i, s in enumerate(SENTENCES) if s.startswith(line)), conf),
    }


def _reader(client: _Client, cap: int = 10**9, notices: list[Any] | None = None,
            ) -> JevReservationFacts:
    return JevReservationFacts(
        client=client,  # type: ignore[arg-type]
        meter=JevArmMeter(max_calls=20, max_cost_nano_usd=cap),
        observed_at=NOW,
        notify_owner=(lambda s, b: notices.append((s, b))) if notices is not None else None,
    )


_UNKNOWN = {"check_in": "2026-11-12", "check_out": "2026-11-15", "booked_total": "unknown",
            "refundability": "unknown"}


def test_jev_fills_what_code_could_not_read_and_marks_the_total() -> None:
    facts, reasons = dict(_UNKNOWN), {"booked_total": "x", "refundability": "y"}
    reader = _reader(_Client(_answers()))
    asyncio.run(reader(TEXT, facts, reasons))
    assert (facts["booked_total"], facts["currency"], facts["booked_total_source"]) == (
        "577.42", "USD", "jev")
    assert facts["refund_deadline"] == "2026-11-07"
    assert reasons == {}
    assert reader.counts == {"filled_total": 1, "filled_refund": 1}


def test_code_facts_stand_and_disagreements_are_counted() -> None:
    facts = {**_UNKNOWN, "booked_total": "500", "currency": "USD", "all_in": "explicit",
             "refundability": "explicit_refundable", "refund_deadline": "2026-11-07"}
    reader = _reader(_Client(_answers()))
    asyncio.run(reader(TEXT, facts, {}))
    assert facts["booked_total"] == "500" and "booked_total_source" not in facts
    assert reader.counts == {"disagree": 1, "agree": 1}


@pytest.mark.parametrize(
    "client",
    [
        _Client(_answers(), _answers(total="1 room € 453")),  # the two runs disagree
        _Client(_answers(conf=0.5)),  # not confident
        _Client(error=True),
    ],
)
def test_unagreed_unconfident_or_failed_answers_change_nothing(client: _Client) -> None:
    facts, reasons = dict(_UNKNOWN), {"booked_total": "x"}
    asyncio.run(_reader(client)(TEXT, facts, reasons))
    assert facts["booked_total"] == "unknown"
    assert reasons == {"booked_total": "x"}


def test_each_page_asks_twice_within_the_cap() -> None:
    client = _Client(_answers())
    reader = _reader(client)
    for _ in range(12):
        asyncio.run(reader(TEXT, dict(_UNKNOWN), {}))
    assert len(client.requests) == 20  # ten pages, two calls each


def test_an_exhausted_daily_cap_sends_nothing() -> None:
    client = _Client(_answers())
    asyncio.run(_reader(client, cap=0)(TEXT, dict(_UNKNOWN), {}))
    assert client.requests == []


def test_first_disagreement_of_the_day_notifies_the_owner_once(tmp_path: Any) -> None:
    from booksaver.infrastructure.persistence.sqlite_store import SqliteStore

    db = tmp_path / "booksaver.db"
    with SqliteStore(db):
        pass
    notices: list[Any] = []
    for _ in range(2):
        reader = _reader(_Client(_answers()), notices=notices)
        facts = {**_UNKNOWN, "booked_total": "500", "currency": "USD", "all_in": "explicit"}
        asyncio.run(reader(TEXT, facts, {}))
        reader.record(db, user_id=4, execution_id="sync")
    assert len(notices) == 1
    assert "Real Person" not in repr(notices) and "577" not in repr(notices)


def test_a_call_cut_off_by_the_deadline_is_still_charged(tmp_path: Any) -> None:
    from booksaver.infrastructure.persistence.price_comparison import SqliteJevPriceRunRepository
    from booksaver.infrastructure.persistence.sqlite_store import SqliteStore

    reader = _reader(_Client())
    reader.meter.admit()  # admitted, then cancelled before any usage came back
    db = tmp_path / "booksaver.db"
    with SqliteStore(db):
        pass
    reader.record(db, user_id=1, execution_id="sync-1")
    with SqliteStore(db) as store:
        assert SqliteJevPriceRunRepository(store).cost_since(datetime(2026, 1, 1, tzinfo=UTC)) > 0


@pytest.mark.parametrize(
    "page",
    [
        [line for line in PAGE if "cancel" not in line.casefold()],  # price lines only
        ["Cancellation policy Non-refundable", "Price", "(for 1 guest)"],  # no amounts
    ],
)
def test_a_page_missing_one_kind_of_candidate_asks_only_what_it_can(page: list[str]) -> None:
    client = _Client({"total": ("m0", 0.9), "refund": ("non_refundable", 0.9),
                      "refund_line": ("r0", 0.9)})
    facts = dict(_UNKNOWN)
    asyncio.run(_reader(client)("\n".join(page), facts, {}))
    asked = set(client.requests[0][1])
    assert asked in ({"total"}, {"refund", "refund_line"})

