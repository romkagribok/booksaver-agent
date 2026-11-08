"""Parse narrowly qualified rendered confirmation facts without browser or persistence access.

The caller owns authentication, destination guards, snapshot capture, and current-run identity
binding. This module cannot prove account coverage or authorize monitoring or absence updates.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from urllib.parse import urlsplit

_MAX_TEXT = 250_000
_MAX_LINES = 8_000
# en-US grouping only: the reader qualifies English pages rendered in the en-US browser locale.
_AMOUNT = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]{1,7})(?:\.[0-9]{1,2})?"
# Dollar currencies are read only with their prefix (the observed page prints "US$309"); a bare
# "$" names no single currency and is not money here.
_CURRENCY_SYMBOLS = {
    "US$": "USD", "CA$": "CAD", "C$": "CAD", "AU$": "AUD", "A$": "AUD", "NZ$": "NZD",
    "HK$": "HKD", "S$": "SGD", "MX$": "MXN", "R$": "BRL", "€": "EUR", "£": "GBP",
    "¥": "JPY", "₹": "INR",
}
_CURRENCY_CODES = (
    "AED", "ARS", "AUD", "AZN", "BGN", "BHD", "BRL", "CAD", "CHF", "CLP", "CNY", "COP",
    "CZK", "DKK", "EGP", "EUR", "FJD", "GBP", "GEL", "HKD", "HUF", "IDR", "ILS", "INR",
    "ISK", "JOD", "JPY", "KRW", "KWD", "KZT", "MDL", "MOP", "MXN", "MYR", "NAD", "NOK",
    "NZD", "OMR", "PLN", "QAR", "RON", "RUB", "SAR", "SEK", "SGD", "THB", "TRY", "TWD",
    "UAH", "USD", "XOF", "ZAR",
)
# Two groups: the currency symbol or ISO code, then the amount. The look-behind keeps a prefixed
# symbol from matching inside a longer one ("S$" inside "US$").
_MONEY = (
    r"(?<![A-Za-z$])(" + "|".join(re.escape(symbol) for symbol in _CURRENCY_SYMBOLS)
    + r"|\b(?:" + "|".join(_CURRENCY_CODES) + r")\b)\s*(" + _AMOUNT + r")"
)
_MONTHS = {
    name: index
    for index, names in enumerate(
        (
            ("Jan", "January"), ("Feb", "February"), ("Mar", "March"),
            ("Apr", "April"), ("May",), ("Jun", "June"), ("Jul", "July"),
            ("Aug", "August"), ("Sep", "September"), ("Oct", "October"),
            ("Nov", "November"), ("Dec", "December"),
        ),
        start=1,
    )
    for name in names
}
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_UNKNOWN_FACTS = (
    "lifecycle", "property_name", "property_reference", "check_in", "check_out",
    "room_type", "booked_total", "currency", "all_in", "refundability",
    "refundability_text", "refund_deadline", "adults", "children", "rooms",
    "meal_plan", "meal_plan_text",
)


def _currency(token: str) -> str:
    return _CURRENCY_SYMBOLS.get(token, token)


def _amount(text: str) -> Decimal:
    return Decimal(text.replace(",", ""))


def _heading(lines: list[str], label: str) -> int | None:
    matches = [
        index for index, line in enumerate(lines)
        if line.rstrip(":").casefold() == label.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def _following(lines: list[str], label: str) -> str | None:
    index = _heading(lines, label)
    return lines[index + 1] if index is not None and index + 1 < len(lines) else None


def _confirmation_heading(lines: list[str]) -> int | None:
    """Locate the unique identity label shared by inline and split confirmation layouts."""
    labels = [
        index
        for index, line in enumerate(lines)
        if line.partition(":")[0].casefold() == "confirmation number"
    ]
    return labels[0] if len(labels) == 1 else None


def _confirmation_value(lines: list[str]) -> str | None:
    """Accept one labeled identity in either observed layout; duplicate labels are ambiguous."""
    index = _confirmation_heading(lines)
    if index is None:
        return None
    inline_value = lines[index].partition(":")[2].strip()
    if inline_value:
        return inline_value
    return lines[index + 1] if index + 1 < len(lines) else None


def _calendar_date(month: str, day: str, year: str) -> date | None:
    try:
        return date(int(year), _MONTHS[month], int(day))
    except (ValueError, KeyError):
        return None


def _stay_date(value: str | None) -> date | None:
    if value is None:
        return None
    match = re.fullmatch(
        r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun), ([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})", value
    )
    if match is None:
        return None
    weekday, month, day, year = match.groups()
    parsed = _calendar_date(month, day, year)
    return parsed if parsed is not None and _WEEKDAYS[parsed.weekday()] == weekday else None


def _property_facts(
    lines: list[str], anchors: tuple[tuple[str, str], ...],
) -> dict[str, str]:
    # The reader supplies only property anchors from the confirmation header, never footer policy
    # or recommendation links. Multiple candidates remain ambiguous even if one looks plausible.
    if len(anchors) != 1:
        return {}
    name, url = anchors[0]
    name = " ".join(name.split())
    check_in = _heading(lines, "Check-in")
    if not 0 < len(name) <= 500 or len(url) > 500 or check_in is None:
        return {}
    if name not in lines[:check_in]:
        return {}
    try:
        parts = urlsplit(url)
        allowed = (
            parts.scheme == "https"
            and parts.hostname in {"www.booking.com", "secure.booking.com"}
            and parts.port is None
            and parts.username is None
            and parts.password is None
            and re.fullmatch(r"/hotel/[a-z]{2}/[A-Za-z0-9._-]+\.html", parts.path)
        )
    except ValueError:
        return {}
    # Tracking parameters are dropped; the property is the allowlisted path.
    reference = f"https://{parts.hostname}{parts.path}"
    return {"property_name": name, "property_reference": reference} if allowed else {}


# Free until one local moment, charged from the next: (until day, minute, from day, minute).
def confirmation_lines(body_text: str) -> list[str]:
    """The page's non-empty lines with whitespace collapsed, as every reader sees them."""
    lines = [" ".join(line.split()) for line in body_text.replace("’", "'").splitlines()]
    return [line for line in lines if line]


def parse_confirmation_facts(
    body_text: str,
    hotel_anchors: tuple[tuple[str, str], ...],
    *,
    observed_at: datetime,
    reasons: dict[str, str] | None = None,
) -> dict[str, str] | None:
    """Return a partial payload for one recognized English confirmation, without guessing facts.

    ``reasons`` receives a fixed, content-free code for an unknown total or refundability.

    Hotel anchors must be captured from the same rendered header before Check-in. Unknown optional
    fields stay ``unknown``; unsupported or contradictory confirmation identity/status returns None.
    """
    if not 0 < len(body_text) <= _MAX_TEXT or len(hotel_anchors) > 8 or observed_at.tzinfo is None:
        return None
    lines = confirmation_lines(body_text)
    if len(lines) > _MAX_LINES or any(len(line) > 8_000 for line in lines):
        return None
    if lines.count("Your stay is confirmed") != 1:
        return None
    if any(
        re.search(
            r"\byour (?:stay|booking|reservation) (?:is|has been) cancel(?:led|ed)\b", line, re.I
        )
        for line in lines
    ):
        return None
    confirmation = _confirmation_value(lines)
    if confirmation is None or re.fullmatch(r"[0-9][0-9 .]{4,28}[0-9]", confirmation) is None:
        return None
    confirmation = confirmation.replace(" ", "").replace(".", "")
    if not 6 <= len(confirmation) <= 20:
        return None
    payload = dict.fromkeys(_UNKNOWN_FACTS, "unknown")
    payload.update({
        "remote_id": confirmation, "confirmation_id": confirmation, "scope": "unknown",
        "identity_evidence": "complete", "completeness": "incomplete",
    })
    today = observed_at.astimezone(UTC).date()
    check_in = _stay_date(_following(lines, "Check-in"))
    check_out = _stay_date(_following(lines, "Check-out"))
    if check_in is not None and check_out is not None and check_in < check_out:
        lifecycle = (
            "completed" if check_out <= today else "current" if check_in <= today else "upcoming"
        )
        payload.update({
            "check_in": check_in.isoformat(), "check_out": check_out.isoformat(),
            "lifecycle": lifecycle, "scope": "past" if lifecycle == "completed" else "upcoming",
        })
    else:
        check_in = check_out = None
    payload.update(_property_facts(lines, hotel_anchors))
    # Total, refund terms, room, party and meals are read by Jev (ADR-061), never by layout code.
    return payload


def parse_cancelled_confirmation(body_text: str) -> dict[str, str] | None:
    """Read a unique confirmation and explicit cancellation, never absence or policy text."""
    if not 0 < len(body_text) <= _MAX_TEXT:
        return None
    lines = [" ".join(line.split()) for line in body_text.replace("’", "'").splitlines()]
    lines = [line for line in lines if line]
    if len(lines) > _MAX_LINES or any(len(line) > 8_000 for line in lines):
        return None
    cancelled = re.compile(
        r"your (?:stay|booking|reservation) (?:is|has been) cancel(?:led|ed)[.!]?", re.I
    )
    if sum(bool(cancelled.fullmatch(line)) for line in lines) != 1:
        return None
    if any(line.casefold().rstrip(".!") in {
        "your stay is confirmed", "your booking is confirmed", "your reservation is confirmed",
        "confirmed", "upcoming", "in progress",
    } for line in lines):
        return None
    confirmation = _confirmation_value(lines)
    if confirmation is None or re.fullmatch(r"[0-9][0-9 .]{4,28}[0-9]", confirmation) is None:
        return None
    confirmation = confirmation.replace(" ", "").replace(".", "")
    if not 6 <= len(confirmation) <= 20:
        return None
    payload = dict.fromkeys(_UNKNOWN_FACTS, "unknown")
    payload.update({
        "remote_id": confirmation, "confirmation_id": confirmation,
        "scope": "cancelled", "lifecycle": "cancelled",
        "identity_evidence": "complete", "completeness": "incomplete",
    })
    return payload
