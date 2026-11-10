"""Jev reads, code wins where it reads (ADR-060). Shapes from the owner's dad's real pages."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from typing import Any

import pytest

from booksaver.infrastructure.browser.inventory_confirmation_facts import confirmation_lines
from booksaver.infrastructure.browser.jev_price_executor import JevArmMeter
from booksaver.infrastructure.browser.jev_reservation_facts import (
    JevReservationFacts,
    cancellation_sentences,
    check_dates,
    check_refund,
    check_total,
    header_lines,
    price_area,
    redact,
    room_candidates,
    room_section_lines,
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
        # The stay in _UNKNOWN is three nights for one adult.
        "adults": ("n1", conf), "children": ("n0", conf), "rooms": ("n1", conf),
        "nights": ("n3", conf),
    }


def _reader(client: _Client, cap: int = 10**9) -> JevReservationFacts:
    return JevReservationFacts(
        client=client,  # type: ignore[arg-type]
        meter=JevArmMeter(max_calls=20, max_cost_nano_usd=cap),
        observed_at=NOW,
    )


_UNKNOWN = {"check_in": "2026-11-12", "check_out": "2026-11-15", "booked_total": "unknown",
            "refundability": "unknown"}


def test_jev_reads_the_total_and_refund_terms() -> None:
    facts, reasons = dict(_UNKNOWN), {}
    reader = _reader(_Client(_answers()))
    asyncio.run(reader(TEXT, facts, reasons))
    assert (facts["booked_total"], facts["currency"], facts["booked_total_source"]) == (
        "577.42", "USD", "jev")
    assert facts["refund_deadline"] == "2026-11-07"
    assert reasons == {}
    assert reader.counts == {"read_booked_total": 1, "read_refundability": 1, "read_party": 1}
    assert (facts["adults"], facts["children"], facts["rooms"]) == ("1", "0", "1")


def test_a_dated_cost_line_gives_the_exact_deadline() -> None:
    assert "until November 7, 2026 11:59 PM: US$0" in SENTENCES
    facts = dict(_UNKNOWN)
    asyncio.run(_reader(_Client(_answers(line="until November 7")))(TEXT, facts, {}))
    assert facts["refund_deadline"] == "2026-11-07"


def test_jev_replaces_whatever_the_page_had_before() -> None:
    facts = {**_UNKNOWN, "booked_total": "500", "currency": "USD", "all_in": "explicit"}
    asyncio.run(_reader(_Client(_answers()))(TEXT, facts, {}))
    assert facts["booked_total"] == "577.42"


def test_calendar_months_are_used_for_within() -> None:
    result = check_refund(
        "free_until_date", "Free cancellation within: 5 months 9 days", date(2027, 4, 15),
        datetime(2026, 11, 4, 6, 8, tzinfo=UTC),
    )
    assert result is not None and result["refund_deadline"] == "2027-04-12"


@pytest.mark.parametrize(
    "client",
    [
        _Client(_answers(), _answers(total="1 room € 453")),  # the two runs disagree
        _Client(_answers(total="1 room € 453")),  # agreed, but a component, not the total
        _Client(error=True),
    ],
)
def test_unagreed_unchecked_or_failed_answers_change_nothing(client: _Client) -> None:
    facts, reasons = dict(_UNKNOWN), {}
    asyncio.run(_reader(client)(TEXT, facts, reasons))
    assert facts["booked_total"] == "unknown"
    assert reasons["booked_total"] in {"jev_unread", "jev_unavailable"}


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
        since = datetime(2026, 1, 1, tzinfo=UTC)
        assert SqliteJevPriceRunRepository(store).cost_since(since, 1) > 0
        assert SqliteJevPriceRunRepository(store).cost_since(since, 2) == 0


def test_the_facts_budget_is_each_users_own_daily_cap(tmp_path: Any) -> None:
    from booksaver.domain.price_comparison import JevComparisonSettings, JevUsage
    from booksaver.infrastructure.browser.jev_reservation_facts import remaining_daily_nano_usd
    from booksaver.infrastructure.persistence.price_comparison import (
        JevPriceRun,
        SqliteJevPriceRunRepository,
    )
    from booksaver.infrastructure.persistence.sqlite_store import SqliteStore

    db = tmp_path / "booksaver.db"
    now = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
    with SqliteStore(db) as store:
        SqliteJevPriceRunRepository(store).record(JevPriceRun(
            execution_id="user-2-today", user_id=2, booking_id="", created_at=now,
            status="observed", usage=JevUsage(calls=9, cost_nano_usd=400_000),
            latency_ms=1, adapter="test",
        ))
    settings = JevComparisonSettings(max_daily_cost_nano_usd=1_000_000)
    assert remaining_daily_nano_usd(db, settings, now, 1) == 1_000_000
    assert remaining_daily_nano_usd(db, settings, now, 2) == 600_000


@pytest.mark.parametrize(
    "page",
    [
        # Price lines only: no cancellation sentence and no dated deadline line.
        [line for line in PAGE if not ("cancel" in line.casefold() or line.startswith("until"))],
        ["Cancellation policy Non-refundable", "Price", "(for 1 guest)"],  # no amounts
    ],
)
def test_a_page_missing_one_kind_of_candidate_asks_only_what_it_can(page: list[str]) -> None:
    client = _Client({"total": ("m0", 0.9), "refund": ("non_refundable", 0.9),
                      "refund_line": ("r0", 0.9)})
    facts = dict(_UNKNOWN)
    asyncio.run(_reader(client)("\n".join(page), facts, {}))
    asked = set(client.requests[0][1]) & {"total", "refund", "refund_line"}
    assert asked in ({"total"}, {"refund", "refund_line"})


def test_an_agreed_total_counts_however_unsure_jev_is() -> None:
    # Park Plaza Lodge: rows in EUR, charged in USD; both runs chose the total at 0.51 and 0.54.
    facts = dict(_UNKNOWN)
    asyncio.run(_reader(_Client(_answers(conf=0.51), _answers(conf=0.54)))(TEXT, facts, {}))
    assert (facts["booked_total"], facts["currency"]) == ("577.42", "USD")


ROOM_TEXT = "\n".join([
    "Your confirmation is on its way to guest@example.com", "Confirmation number:6918993423",
    "PIN:5140", "Your room details", "Private suite", "Deluxe Queen Bed", "Change your room",
    "Guest name", "Real Person Edit guest name", *PAGE,
])
_ROOM_OPTIONS = room_candidates(confirmation_lines(ROOM_TEXT))


def _with_room(room: str, conf: float = 0.9) -> dict[str, Any]:
    return {**_answers(), "room": (f"l{_ROOM_OPTIONS.index(room)}", conf)}


def test_jev_reads_the_room_type_of_a_single_room_stay() -> None:
    facts, reasons = {**_UNKNOWN, "rooms": "1", "room_type": "unknown"}, {}
    reader = _reader(_Client(_with_room("Deluxe Queen Bed")))
    asyncio.run(reader(ROOM_TEXT, facts, reasons))
    assert facts["room_type"] == "Deluxe Queen Bed" and "room_type" not in reasons
    assert reader.counts["read_room_type"] == 1


@pytest.mark.parametrize(
    "client",
    [
        _Client(_with_room("Deluxe Queen Bed"), _with_room("Private suite")),
        _Client(_with_room("Deluxe Queen Bed", conf=0.4)),
    ],
)
def test_an_unagreed_or_unsure_room_stays_unknown(client: _Client) -> None:
    facts, reasons = {**_UNKNOWN, "rooms": "1", "room_type": "unknown"}, {}
    asyncio.run(_reader(client)(ROOM_TEXT, facts, reasons))
    assert facts["room_type"] == "unknown" and reasons["room_type"] == "jev_unread"


def test_a_multi_room_party_gets_no_room_type() -> None:
    facts = {**_UNKNOWN, "room_type": "unknown"}
    client = _Client({**_with_room("Deluxe Queen Bed"), "rooms": ("n2", 0.9)})
    text = "Booking Details\n1 adult - 3 nights, 2 rooms\n" + ROOM_TEXT
    asyncio.run(_reader(client)(text, facts, {}))
    assert facts["rooms"] == "2" and facts["room_type"] == "unknown"


def test_room_candidates_are_the_room_section_only() -> None:
    assert _ROOM_OPTIONS == ["Private suite", "Deluxe Queen Bed"]
    client = _Client(_with_room("Deluxe Queen Bed"))
    asyncio.run(_reader(client)(ROOM_TEXT, {**_UNKNOWN, "rooms": "1", "room_type": "unknown"}, {}))
    sent = repr(client.requests)
    for personal in ("guest@example.com", "6918993423", "5140", "Real Person"):
        assert personal not in sent


def test_a_party_needs_every_count_and_nights_matching_the_stay() -> None:
    facts: dict[str, str] = {**_UNKNOWN, "adults": "unknown"}
    asyncio.run(_reader(_Client({**_answers(), "children": ("n2", 0.9)}))(TEXT, facts, {}))
    assert (facts["adults"], facts["children"], facts["rooms"]) == ("1", "2", "1")
    for wrong in ({"nights": ("n2", 0.9)}, {"adults": ("not_stated", 0.9)}):
        facts, reasons = {**_UNKNOWN, "adults": "unknown"}, {}
        asyncio.run(_reader(_Client({**_answers(), **wrong}))(TEXT, facts, reasons))
        assert facts["adults"] == "unknown" and reasons["party"] == "jev_unread"


MEAL_TEXT = "\n".join([
    "Your room details", "Standard Double Room", "Guest name", "Real Person",
    "Meal Plan", "Breakfast is included in the room rate.", "Phone +1 323 931 1501", *PAGE,
])
_MEAL_LINES = room_section_lines(confirmation_lines(MEAL_TEXT))


def _meal(meal: str, line: str | None = None) -> dict[str, Any]:
    chosen = f"s{_MEAL_LINES.index(line)}" if line else "none"
    return {**_answers(), "meal": (meal, 0.9), "meal_line": (chosen, 0.9)}


def test_jev_classifies_the_meal_plan_and_keeps_its_line() -> None:
    facts = {**_UNKNOWN, "meal_plan": "unknown"}
    line = "Breakfast is included in the room rate."
    asyncio.run(_reader(_Client(_meal("breakfast", line)))(MEAL_TEXT, facts, {}))
    assert (facts["meal_plan"], facts["meal_plan_text"]) == ("breakfast", line)


def test_meals_not_stated_or_unagreed_stay_unknown() -> None:
    line = "Breakfast is included in the room rate."
    for client in (
        _Client(_meal("not_stated")),
        _Client(_meal("breakfast"), _meal("none")),
        _Client(_meal("none")),  # agreed class, no line stating it
        _Client(_meal("none", line), _meal("none", "Standard Double Room")),  # lines disagree
    ):
        facts, reasons = {**_UNKNOWN, "meal_plan": "unknown"}, {}
        asyncio.run(_reader(client)(MEAL_TEXT, facts, reasons))
        assert facts["meal_plan"] == "unknown" and reasons["meal_plan"] == "jev_unread"


def test_the_guest_name_and_phone_never_reach_jev() -> None:
    assert "Real Person" not in _MEAL_LINES and "Guest name" not in _MEAL_LINES
    assert not any("+1" in line for line in _MEAL_LINES + header_lines(confirmation_lines(
        "Your stay is confirmed\nPhone +1 323 931 1501\nReal Person, guest@example.com"
    )))


def test_dates_code_could_not_read_are_read_by_jev() -> None:
    answers = {
        **_answers(), "check_in_month": ("n11", 0.9), "check_in_day": ("n12", 0.9),
        "check_in_year": ("n2026", 0.9), "check_out_month": ("n11", 0.9),
        "check_out_day": ("n15", 0.9), "check_out_year": ("n2026", 0.9),
    }
    facts = {**_UNKNOWN, "check_in": "unknown", "check_out": "unknown", "lifecycle": "unknown"}
    client = _Client(answers)
    asyncio.run(_reader(client)(TEXT, facts, {}))
    assert (facts["check_in"], facts["check_out"], facts["lifecycle"]) == (
        "2026-11-12", "2026-11-15", "upcoming")
    assert facts["refund_deadline"] == "2026-11-07"  # the refund check used Jev's dates
    known = _Client(_answers())
    asyncio.run(_reader(known)(TEXT, dict(_UNKNOWN), {}))
    assert not any("check_in_day" in questions for _, questions in known.requests)


def test_impossible_dates_are_rejected() -> None:
    assert check_dates([2, 30, 2027, 3, 1, 2027], date(2026, 11, 8)) is None
    assert check_dates([3, 1, 2027, 2, 27, 2027], date(2026, 11, 8)) is None
    assert check_dates([1, 1, 2027, 6, 1, 2027], date(2026, 11, 8)) is None  # over 90 nights


def test_personal_labels_take_their_values_with_them() -> None:
    page = [
        "Your stay is confirmed", "Confirmation number", "1234 567 890", "PIN", "9876",
        "Booking Details", "2 adults - 1 night, 1 rooms", "Guest name:", "Real Person",
        "Ref 1234.567.890", "Phone: 555 0100",
    ]
    kept = redact(page, "1234567890")
    assert kept == ["Your stay is confirmed", "Booking Details", "2 adults - 1 night, 1 rooms"]
    # The spaced number is caught even without knowing the confirmation id.
    assert "1234 567 890" not in header_lines(page)


def test_a_page_with_a_spaced_confirmation_and_pin_sends_neither() -> None:
    text = "\n".join(["Confirmation number", "1234 567 890", "PIN", "9876", *PAGE])
    client = _Client(_answers())
    facts = {**_UNKNOWN, "confirmation_id": "1234567890"}
    asyncio.run(_reader(client)(text, facts, {}))
    sent = repr(client.requests)
    assert "1234 567 890" not in sent and "9876" not in sent


@pytest.mark.parametrize("value", ["2026-11-12", "12.11.2026", "11/12/2026", "Thu 12.11.2026"])
def test_numeric_stay_dates_reach_jev_but_long_numbers_do_not(value: str) -> None:
    kept = header_lines(["Check-in", value, "Phone 555 010 0123", "Ref 1234 5678 90"])
    assert kept == ["Check-in", value]


def test_trip_cards_are_classified_only_where_both_asks_agree_surely() -> None:
    cards = [["AIRINN Vilnius Airport Hotel", "Nov 10 – Nov 11", "Confirmed"],
             ["BMW X1 or similar", "Nov 12 – Nov 20", "Confirmed"],
             ["Get the free app", "Guest name", "Jane Doe", "Booker: John Smith", "Install"]]
    client = _Client(
        {"c0": ("stay_active", 0.97), "c1": ("other_active", 0.95), "c2": ("not_a_booking", 0.9)},
        {"c0": ("stay_active", 0.93), "c1": ("other_inactive", 0.95), "c2": ("not_a_booking", 0.7)},
    )
    assert asyncio.run(_reader(client).classify_cards(cards)) == ["stay_active", None, None]
    state, questions = client.requests[0]
    assert state == {}
    assert not {"Jane", "John", "Guest name", "Booker"} & set(json.dumps(questions).split())
    assert "Jane Doe" not in json.dumps(questions) and "John Smith" not in json.dumps(questions)
    assert "BMW X1 or similar | Nov 12 – Nov 20 | Confirmed" in json.dumps(questions["c1"],
                                                                        ensure_ascii=False)


def test_trip_cards_need_both_asks_and_respect_the_budget() -> None:
    cards = [["Hotel", "Confirmed"]]
    assert asyncio.run(_reader(_Client(error=True)).classify_cards(cards)) is None
    assert asyncio.run(_reader(_Client({"c0": ("stay_active", 1.0)}), cap=0)
                       .classify_cards(cards)) is None
    assert asyncio.run(_reader(_Client()).classify_cards([])) == []
