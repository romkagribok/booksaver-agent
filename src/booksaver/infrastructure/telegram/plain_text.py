"""Plain wording shared by every report a user reads (intent 040): no IDs, codes or profiles."""

from __future__ import annotations

from datetime import UTC, date, datetime

from booksaver.domain.check_result import FailureCode, FailureReason
from booksaver.domain.mobile_web import GeniusEvidence, PriceSourceProvenance
from booksaver.domain.value_objects import Money

_RETRY = "the next check will try again"
_FAILURES = {
    FailureCode.AUTH_REQUIRED: "Booking.com sign-in is needed; send /connect",
    FailureCode.TIMEOUT: f"the check took too long; {_RETRY}",
    FailureCode.TIME_LIMIT: f"the check took too long; {_RETRY}",
    FailureCode.OCCUPANCY_MISSING: "the number of guests on your booking is unknown",
    FailureCode.PROPERTY_NOT_FOUND: "the hotel's page could not be found",
    FailureCode.CURRENCY_MISMATCH: "prices were shown in another currency than your booking",
    FailureCode.BOT_WALL: f"Booking.com asked for a robot check; {_RETRY}",
    FailureCode.BUDGET_EXCEEDED: "skipped: today's price-check budget is used up",
    FailureCode.JOB_COST_LIMIT: "skipped: today's price-check budget is used up",
    FailureCode.DAILY_COST_LIMIT: "skipped: today's price-check budget is used up",
    FailureCode.USER_CHECK_LIMIT_REACHED: "skipped: today's check limit is reached",
    FailureCode.CALLER_REVOKED: "skipped: your access is paused",
    FailureCode.PROVIDER_AUTHENTICATION: f"the price reader was unavailable; {_RETRY}",
    FailureCode.PROVIDER_UNAVAILABLE: f"the price reader was unavailable; {_RETRY}",
    FailureCode.PROVIDER_RATE_LIMIT: f"the price reader was busy; {_RETRY}",
}


def day(value: date) -> str:
    return f"{value.day} {value:%b %Y}"


def stay(check_in: date, check_out: date) -> str:
    if check_in.year != check_out.year:
        return f"{day(check_in)} – {day(check_out)}"
    if check_in.month != check_out.month:
        return f"{check_in.day} {check_in:%b} – {day(check_out)}"
    return f"{check_in.day} – {day(check_out)}"


def moment(value: datetime) -> str:
    value = value.astimezone(UTC)
    return f"{value.day} {value:%b}, {value:%H:%M} UTC"


def money(value: Money) -> str:
    return f"{value.amount} {value.currency}"


def versus_paid(live: Money, paid: Money) -> str:
    """How a live price compares with what was paid, e.g. "3.78 USD below what you paid"."""
    if live.currency != paid.currency:
        return f"your booking is in {paid.currency}"
    difference = paid.amount - live.amount
    if difference == 0:
        return "the same as you paid"
    side = "below" if difference > 0 else "above"
    return f"{abs(difference)} {paid.currency} {side} what you paid"


def failure_text(reason: FailureReason) -> str:
    if reason.code is FailureCode.NO_EQUIVALENT_OFFER:
        if "availability" in reason.detail.casefold():
            return "no rooms available for your dates"
        return "no offer matched your room, meals and cancellation terms"
    return _FAILURES.get(reason.code, f"the price page could not be read; {_RETRY}")


def checked_as(source: PriceSourceProvenance) -> str:
    text = "signed in to your Booking.com account"
    if source.genius_evidence is GeniusEvidence.APPLIED_OR_PRESENT:
        text += " (Genius prices were shown)"
    return text
