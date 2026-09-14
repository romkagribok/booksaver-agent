"""Parse narrowly qualified rendered confirmation facts without browser or persistence access.

The caller owns authentication, destination guards, snapshot capture, and current-run identity
binding. This module cannot prove account coverage or authorize monitoring or absence updates.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlsplit

_MAX_TEXT = 250_000
_MAX_LINES = 8_000
_AMOUNT = r"[0-9]{1,7}(?:\.[0-9]{1,2})?"
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
_FINAL_PRICE_STATEMENTS = frozenset({
    "The final price shown is the amount you'll pay to the property.",
    "The final price shown is the amount you will pay to the property.",
})
_OPTIONAL_CHARGE_NOTICES = frozenset({
    "Note that additional supplements (e.g. an extra bed) aren't added in this total.",
    "Note that additional supplements (e.g. an extra bed) are not added in this total.",
    (
        "Guests are required to show a photo ID and credit card upon check-in. "
        "Please note that all Special Requests are subject to availability and additional charges "
        "may apply."
    ),
})
_ADDITIONAL_CHARGES_NOTICE = (
    "The price you see below is an approximate that may include fees based on the maximum "
    "occupancy. This can include taxes set by local governments or charges set by the property."
)
_UNKNOWN_FACTS = (
    "lifecycle", "property_name", "property_reference", "check_in", "check_out",
    "room_type", "booked_total", "currency", "all_in", "refundability",
    "refundability_text", "refund_deadline", "adults", "children", "rooms",
)


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
            and not parts.query
            and not parts.fragment
            and re.fullmatch(r"/hotel/[a-z]{2}/[A-Za-z0-9._-]+\.html", parts.path)
        )
    except ValueError:
        return {}
    return {"property_name": name, "property_reference": url} if allowed else {}


def _guest_facts(
    lines: list[str], check_in: date | None, check_out: date | None,
) -> tuple[dict[str, str], int | None]:
    boundary = _confirmation_heading(lines)
    if boundary is None:
        return {}, None
    # Later page navigation repeats "Booking Details" without describing the booked party.
    # Only the unique composition label inside this confirmation's header can supply guests.
    value = _following(lines[:boundary], "Booking Details")
    if value is None or check_in is None or check_out is None:
        return {}, None
    # This is a closed booked-party composition, not a capacity or generic guest-count label.
    match = re.fullmatch(
        r"([1-9][0-9]?) adults? - ([1-9][0-9]?) (nights?|weeks?), "
        r"1 (rooms?|apartments?)", value,
    )
    if match is None:
        return {}, None
    adults, length, duration, _unit = match.groups()
    nights = int(length) * (7 if duration.startswith("week") else 1)
    if (check_out - check_in).days != nights:
        return {}, None
    return {"adults": adults, "children": "0", "rooms": "1"}, nights


def _room_fact(lines: list[str], single_unit: bool) -> str | None:
    if not single_unit:
        return None
    index = _heading(lines, "Your room details")
    if index is None or index + 2 >= len(lines):
        return None
    index += 1
    if lines[index] == "Entire apartment":
        index += 1
    if index + 1 >= len(lines) or lines[index + 1] not in {"Change your room", "Guest name"}:
        return None
    value = lines[index]
    return value if 0 < len(value) <= 500 else None


def _cancellation_facts(lines: list[str], observed_at: datetime) -> dict[str, str]:
    index = _heading(lines, "Cancellation cost")
    if index is None:
        return {}
    # Only the two explicit cost tiers in this confirmation's cancellation section qualify.
    tiers: dict[str, tuple[date, int, Decimal]] = {}
    section_ended = False
    for line in lines[index + 1:index + 16]:
        if re.match(r"1 (room|apartment)\b", line) or line in {"Price", "Price breakdown"}:
            section_ended = True
            break
        if not line.startswith(("until ", "from ")):
            continue
        match = re.fullmatch(
            r"(until|from) ([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4}) "
            r"([0-9]{1,2}):([0-9]{2}) (AM|PM): €\s*(" + _AMOUNT + r")"
            r"(?: – Changing the dates of your stay isn't possible\.)?", line,
        )
        if match is None:
            return {}
        kind, month, day, year, hour, minute, meridiem, amount = match.groups()
        parsed = _calendar_date(month, day, year)
        if parsed is None or not 1 <= int(hour) <= 12 or int(minute) > 59 or kind in tiers:
            return {}
        minutes = (int(hour) % 12 + (12 if meridiem == "PM" else 0)) * 60 + int(minute)
        tiers[kind] = parsed, minutes, Decimal(amount)
    if not section_ended or set(tiers) != {"until", "from"}:
        return {}
    until_day, until_minute, until_cost = tiers["until"]
    from_day, from_minute, from_cost = tiers["from"]
    gap = (from_day - until_day).days * 1440 + from_minute - until_minute
    if until_cost != 0 or from_cost <= 0 or not 0 <= gap <= 1:
        return {}
    # The snapshot has no verified property timezone. Today's local cutoff stays unknown. At
    # adjacent UTC dates, require the result to hold even at the earliest/latest real-world offset
    # instead of treating a UTC date as the property's local date.
    now = observed_at.astimezone(UTC)
    until_time = datetime.combine(until_day, datetime.min.time(), UTC) + timedelta(
        minutes=until_minute
    )
    from_time = datetime.combine(from_day, datetime.min.time(), UTC) + timedelta(
        minutes=from_minute
    )
    try:
        earliest_cutoff = until_time - timedelta(hours=14)
        latest_charge_start = from_time + timedelta(hours=12)
    except OverflowError:
        return {}
    if until_day > now.date() and now < earliest_cutoff:
        return {
            "refundability": "explicit_refundable",
            "refund_deadline": until_day.isoformat(),
            "refundability_text": (
                f"Free cancellation until {until_day.isoformat()} (property time)."
            ),
        }
    if from_day < now.date() and now >= latest_charge_start:
        return {
            "refundability": "explicit_nonrefundable",
            "refundability_text": "The displayed free-cancellation period has expired.",
        }
    return {}


def _price_facts(lines: list[str], guests: dict[str, str], nights: int | None) -> dict[str, str]:
    if not guests or nights is None:
        return {}
    statements = [i for i, line in enumerate(lines) if line in _FINAL_PRICE_STATEMENTS]
    price_index = _heading(lines, "Price")
    if len(statements) != 1 or price_index is None:
        return {}
    end = statements[0]
    if end not in {price_index + 3, price_index + 9}:
        return {}
    if lines[price_index + 1] != f"(for {guests['adults']} guests)":
        return {}
    total_match = re.fullmatch(r"€\s*(" + _AMOUNT + r")", lines[price_index + 2])
    if total_match is None:
        return {}
    total = Decimal(total_match[1])
    if total <= 0:
        return {}

    final_total = total
    additional_city = Decimal(0)
    qualified_notice_indexes: set[int] = set()
    if end == price_index + 9:
        # The generic maximum-occupancy notice is resolved only for this exact closed-party
        # calculation. Every line in the additional-charge block must match the observed shape.
        if (
            _heading(lines, "Additional charges") != price_index + 3
            or lines[price_index + 4] != _ADDITIONAL_CHARGES_NOTICE
            or _heading(lines, "Final Price") != price_index + 6
            or lines[price_index + 7] != "(taxes included)"
        ):
            return {}
        city = re.fullmatch(
            r"City tax \(€\s*(" + _AMOUNT + r") × ([1-9][0-9]?) guests? × "
            r"([1-9][0-9]?) nights?\) €\s*(" + _AMOUNT + r")",
            lines[price_index + 5],
        )
        final = re.fullmatch(r"€\s*(" + _AMOUNT + r")", lines[price_index + 8])
        if city is None or final is None:
            return {}
        rate, party, duration, amount = city.groups()
        additional_city = Decimal(amount)
        final_total = Decimal(final[1])
        if (
            int(party) != int(guests["adults"])
            or int(duration) != nights
            or Decimal(rate) <= 0
            or additional_city != Decimal(rate) * int(party) * int(duration)
            or final_total != total + additional_city
        ):
            return {}
        qualified_notice_indexes = {price_index + 3, price_index + 4}
    elif any(line.rstrip(":").casefold() == "final price" for line in lines):
        return {}

    # These exact notices concern optional extras or special requests. Every other charge warning
    # makes this narrowly qualified total insufficient, wherever it is rendered.
    other_text = " ".join(
        line for i, line in enumerate(lines)
        if line not in _OPTIONAL_CHARGE_NOTICES and i not in qualified_notice_indexes
    ).casefold()
    if re.search(
        r"additional charges|approximate|not included|excluded|not added|aren't added|"
        r"payable separately|collected separately|paid separately|extra (?:tax|fee|charge)|"
        r"(?:tax|fee).{0,80}(?:pay at|paid at|collected at)", other_text,
    ):
        return {}
    room_rows = [
        (i, re.fullmatch(r"1 (?:room|apartment) €\s*(" + _AMOUNT + r")", line))
        for i, line in enumerate(lines[:price_index])
    ]
    room_rows = [(i, match) for i, match in room_rows if match is not None]
    if len(room_rows) != 1:
        return {}
    start, room_match = room_rows[0]
    assert room_match is not None
    if price_index - start > 4:
        return {}
    room_amount = Decimal(room_match[1])
    charges = room_amount
    seen: set[str] = set()
    for line in lines[start + 1:price_index]:
        vat = re.fullmatch(r"([0-9]{1,2}(?:\.[0-9]{1,2})?) % VAT €\s*(" + _AMOUNT + r")", line)
        city = re.fullmatch(
            r"€\s*(" + _AMOUNT + r") City tax per person per night €\s*(" + _AMOUNT + r")", line
        )
        if vat is not None and "vat" not in seen:
            rate, amount = Decimal(vat[1]), Decimal(vat[2])
            expected = (room_amount * rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if amount != expected:
                return {}
            seen.add("vat")
        elif city is not None and "city" not in seen and not additional_city:
            rate, amount = Decimal(city[1]), Decimal(city[2])
            if amount != rate * int(guests["adults"]) * nights:
                return {}
            seen.add("city")
        else:
            return {}
        charges += amount
    if charges != total:
        return {}
    # An unmatched monetary fee/tax row invalidates either layout, including rows below the
    # final-price statement. Only the additional layout has a reconciled row after its subtotal.
    recognized_rows = set(range(start, price_index))
    if additional_city:
        recognized_rows.add(price_index + 5)
    if any(
        index not in recognized_rows
        and "€" in line
        and re.search(r"\b(?:tax(?:es)?|fees?|charges?)\b", line, re.I)
        for index, line in enumerate(lines)
    ):
        return {}
    return {"booked_total": str(final_total), "currency": "EUR", "all_in": "explicit"}


def parse_confirmation_facts(
    body_text: str,
    hotel_anchors: tuple[tuple[str, str], ...],
    *,
    observed_at: datetime,
) -> dict[str, str] | None:
    """Return a partial payload for one recognized English confirmation, without guessing facts.

    Hotel anchors must be captured from the same rendered header before Check-in. Unknown optional
    fields stay ``unknown``; unsupported or contradictory confirmation identity/status returns None.
    """
    if not 0 < len(body_text) <= _MAX_TEXT or len(hotel_anchors) > 8 or observed_at.tzinfo is None:
        return None
    lines = [" ".join(line.split()) for line in body_text.replace("’", "'").splitlines()]
    lines = [line for line in lines if line]
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
    guests, nights = _guest_facts(lines, check_in, check_out)
    payload.update(guests)
    room = _room_fact(lines, bool(guests))
    if room is not None:
        payload["room_type"] = room
    payload.update(_cancellation_facts(lines, observed_at))
    payload.update(_price_facts(lines, guests, nights))
    return payload
