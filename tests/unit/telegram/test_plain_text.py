from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from booksaver.domain.check_result import FailureCode, FailureReason
from booksaver.domain.value_objects import Money
from booksaver.infrastructure.telegram.plain_text import (
    failure_text,
    moment,
    stay,
    versus_paid,
)


@pytest.mark.parametrize(
    ("check_in", "check_out", "text"),
    [
        (date(2026, 11, 12), date(2026, 11, 15), "12 – 15 Nov 2026"),
        (date(2026, 11, 29), date(2026, 12, 2), "29 Nov – 2 Dec 2026"),
        (date(2026, 12, 30), date(2027, 1, 2), "30 Dec 2026 – 2 Jan 2027"),
    ],
)
def test_stays_read_as_dates(check_in: date, check_out: date, text: str) -> None:
    assert stay(check_in, check_out) == text


def test_moments_are_short_and_in_utc() -> None:
    assert moment(datetime(2026, 11, 10, 18, 54, 55, tzinfo=UTC)) == "10 Nov, 18:54 UTC"


@pytest.mark.parametrize(
    ("live", "text"),
    [
        (Money(Decimal("144"), "USD"), "3.78 USD below what you paid"),
        (Money(Decimal("157"), "USD"), "9.22 USD above what you paid"),
        (Money(Decimal("147.78"), "USD"), "the same as you paid"),
        (Money(Decimal("132"), "EUR"), "your booking is in USD"),
    ],
)
def test_live_prices_compare_with_what_was_paid(live: Money, text: str) -> None:
    assert versus_paid(live, Money(Decimal("147.78"), "USD")) == text


@pytest.mark.parametrize("code", list(FailureCode))
def test_every_failure_reads_without_its_code(code: FailureCode) -> None:
    text = failure_text(FailureReason(code=code, detail="internal detail"))
    assert code.value not in text and "internal detail" not in text and text


def test_no_availability_is_told_apart_from_no_matching_offer() -> None:
    unavailable = FailureReason(
        FailureCode.NO_EQUIVALENT_OFFER, "The property shows no availability"
    )
    unmatched = FailureReason(FailureCode.NO_EQUIVALENT_OFFER, "No matching room type found")
    assert failure_text(unavailable) == "no rooms available for your dates"
    assert failure_text(unmatched) == "no offer matched your room, meals and cancellation terms"


def test_only_the_daily_limit_says_todays_budget_is_used_up() -> None:
    for code in (FailureCode.BUDGET_EXCEEDED, FailureCode.JOB_COST_LIMIT):
        assert "today" not in failure_text(FailureReason(code, ""))
    assert "today's" in failure_text(FailureReason(FailureCode.DAILY_COST_LIMIT, ""))
