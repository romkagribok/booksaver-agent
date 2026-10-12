"""Parse narrowly qualified rendered confirmation facts without browser or persistence access.

The caller owns authentication, destination guards, snapshot capture, and current-run identity
binding. This module cannot prove account coverage or authorize monitoring or absence updates.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlsplit

from booksaver.domain.meal_plan import (
    MAX_MEAL_PLAN_TEXT,
    MealPlan,
    classify_meal_text,
    mentions_meals,
)

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
    "meal_plan", "meal_plan_text",
)
_MEAL_LABEL = re.compile(r"(?:meal plan|meal option|meals):?(?: (.+))?", re.IGNORECASE)
_ROOM_SECTION_END = frozenset({"cancellation cost", "price", "price breakdown", "additional info"})
# A facilities list describes the room, not the booked rate, even when it names a meal.
_FACILITIES_LABEL = re.compile(r"(?:room )?(?:facilities|amenities):?( .+)?", re.IGNORECASE)


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


def _is_facilities_value(section: list[str], index: int) -> bool:
    inline = _FACILITIES_LABEL.fullmatch(section[index])
    if inline is not None and inline.group(1):
        return True
    previous = _FACILITIES_LABEL.fullmatch(section[index - 1]) if index else None
    return previous is not None and not previous.group(1)


def _meal_facts(lines: list[str], room_found: bool) -> dict[str, str]:
    """Read the booked meal plan from the room details section, never from the rest of the page.

    A labelled row is authoritative. Without one, standalone meal wording in the section counts.
    A section with a guest row and no meal wording at all means no meals; that silent reading
    carries no text so a later explicit statement can replace it.
    """
    start = _heading(lines, "Your room details")
    if start is None or not room_found:
        return {}
    section: list[str] = []
    for line in lines[start + 1:start + 61]:
        if line.rstrip(":").casefold() in _ROOM_SECTION_END:
            break
        section.append(line)
    # (wording to classify, wording to keep). An inline value is classified with its label so
    # "Meals are not included" is not cut down to "are not included".
    labelled: list[tuple[str, str]] = []
    for index, line in enumerate(section):
        match = _MEAL_LABEL.fullmatch(line)
        if match is None:
            continue
        following = section[index + 1] if index + 1 < len(section) else ""
        labelled.append((line, match.group(1)) if match.group(1) else (following, following))
    stated = labelled or [
        (line, line)
        for index, line in enumerate(section)
        if mentions_meals(line) and not _is_facilities_value(section, index)
    ]
    if not stated:
        guest_row = any(line.casefold().startswith("guest name") for line in section)
        return {"meal_plan": MealPlan.NONE.value} if guest_row else {}
    readings = [(classify_meal_text(wording), kept) for wording, kept in stated]
    plans = {plan for plan, _ in readings}
    plan = next(iter(plans)) if len(plans) == 1 else MealPlan.UNKNOWN
    if not labelled:
        # Unlabelled lines may also price an optional extra; an inclusion among them still stands.
        included = plans - {MealPlan.NONE, MealPlan.UNKNOWN}
        if len(included) == 1 and MealPlan.UNKNOWN not in plans:
            plan = next(iter(included))
        if plan is MealPlan.UNKNOWN:
            # Unrecognized free text in the section may be the guest's own; it is not kept.
            return {"meal_plan": plan.value}
    text = next((kept for found, kept in readings if found is plan), readings[0][1])
    return {"meal_plan": plan.value, "meal_plan_text": text[:MAX_MEAL_PLAN_TEXT]}


# Free until one local moment, charged from the next: (until day, minute, from day, minute).
_RefundWindow = tuple[date, int, date, int]
_REFUND_SCHEDULE = re.compile(
    r"You'll get a full refund if you cancel before ([0-9]{1,2}):([0-9]{2}) (AM|PM) on "
    r"([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})\. If you cancel after ([0-9]{1,2}):([0-9]{2}) "
    r"(AM|PM) on ([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4}), you won't be eligible for a refund\."
)


def _clock_minutes(hour: str, minute: str, meridiem: str) -> int | None:
    if not 1 <= int(hour) <= 12 or int(minute) > 59:
        return None
    return (int(hour) % 12 + (12 if meridiem == "PM" else 0)) * 60 + int(minute)


def _cost_tier_window(lines: list[str]) -> tuple[bool, _RefundWindow | None]:
    """Return whether any cost tier is rendered, and the free-then-paid window the tiers prove."""
    index = _heading(lines, "Cancellation cost")
    if index is None:
        return False, None
    # Only the two explicit cost tiers in this confirmation's cancellation section qualify.
    tiers: dict[str, tuple[date, int, str, Decimal]] = {}
    section_ended = False
    rendered = False
    for line in lines[index + 1:index + 16]:
        if re.match(r"1 (room|apartment)\b", line) or line in {"Price", "Price breakdown"}:
            section_ended = True
            break
        if not line.startswith(("until ", "from ")):
            continue
        rendered = True
        match = re.fullmatch(
            r"(until|from) ([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4}) "
            r"([0-9]{1,2}):([0-9]{2}) (AM|PM): " + _MONEY
            + r"(?: – Changing the dates of your stay isn't possible\.)?", line,
        )
        if match is None:
            return True, None
        kind, month, day, year, hour, minute, meridiem, token, amount = match.groups()
        parsed = _calendar_date(month, day, year)
        minutes = _clock_minutes(hour, minute, meridiem)
        if parsed is None or minutes is None or kind in tiers:
            return True, None
        tiers[kind] = parsed, minutes, _currency(token), _amount(amount)
    if not rendered:
        return False, None
    if not section_ended or set(tiers) != {"until", "from"}:
        return True, None
    until_day, until_minute, until_currency, until_cost = tiers["until"]
    from_day, from_minute, from_currency, from_cost = tiers["from"]
    if until_currency != from_currency or until_cost != 0 or from_cost <= 0:
        return True, None
    return True, (until_day, until_minute, from_day, from_minute)


def _refund_schedule_window(lines: list[str]) -> _RefundWindow | None:
    """Read the single full-refund-then-no-refund sentence rendered beside "Refund schedule"."""
    labels = [index for index, line in enumerate(lines) if line.startswith("Refund schedule")]
    if len(labels) != 1:
        return None
    index = labels[0]
    sentence = lines[index].removeprefix("Refund schedule").strip()
    if not sentence and index + 1 < len(lines):
        sentence = lines[index + 1]
    match = _REFUND_SCHEDULE.fullmatch(sentence)
    if match is None:
        return None
    (
        until_hour, until_min, until_meridiem, until_month, until_date, until_year,
        from_hour, from_min, from_meridiem, from_month, from_date, from_year,
    ) = match.groups()
    until_day = _calendar_date(until_month, until_date, until_year)
    from_day = _calendar_date(from_month, from_date, from_year)
    until_minute = _clock_minutes(until_hour, until_min, until_meridiem)
    from_minute = _clock_minutes(from_hour, from_min, from_meridiem)
    if until_day is None or from_day is None or until_minute is None or from_minute is None:
        return None
    return until_day, until_minute, from_day, from_minute


def _cancellation_facts(lines: list[str], observed_at: datetime) -> dict[str, str] | str:
    """Return refundability facts, or the fixed reason code for leaving them unknown."""
    # Rendered cost tiers stay authoritative. The refund schedule sentence is read only on the
    # confirmation layout that prints no cost tiers at all.
    tiers_rendered, window = _cost_tier_window(lines)
    if not tiers_rendered:
        window = _refund_schedule_window(lines)
    if window is None:
        if tiers_rendered:
            return "cost_tiers_unrecognized"
        if any(line.startswith("Refund schedule") for line in lines):
            return "refund_schedule_unrecognized"
        return "no_cancellation_evidence"
    until_day, until_minute, from_day, from_minute = window
    gap = (from_day - until_day).days * 1440 + from_minute - until_minute
    if not 0 <= gap <= 1:
        return "cutoffs_not_adjacent"
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
        return "cutoff_out_of_range"
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
    return "deadline_not_provable"


def _price_facts(
    lines: list[str], guests: dict[str, str], nights: int | None,
) -> dict[str, str] | str:
    """Return the reconciled all-in total, or the fixed reason code for leaving it unknown."""
    if not guests or nights is None:
        return "guest_composition"
    statements = [i for i, line in enumerate(lines) if line in _FINAL_PRICE_STATEMENTS]
    price_index = _heading(lines, "Price")
    if price_index is None:
        return "price_heading"
    # The observed dollar layout prints no final-price statement: the total is closed directly by
    # the "Additional Info" heading and must then be proven tax-inclusive by its own tax row.
    statement_free = (
        not statements
        and price_index + 3 < len(lines)
        and lines[price_index + 3] == "Additional Info"
    )
    if len(statements) != 1 and not statement_free:
        return "final_price_statement"
    end = price_index + 3 if statement_free else statements[0]
    if end not in {price_index + 3, price_index + 9}:
        return "price_block_shape"
    if lines[price_index + 1] != f"(for {guests['adults']} guests)":
        return "guest_count_line"
    total_match = re.fullmatch(_MONEY, lines[price_index + 2])
    if total_match is None:
        return "total_not_money"
    # Every amount that reconciles this total must be printed in the total's own currency.
    currency = _currency(total_match[1])
    total = _amount(total_match[2])
    if total <= 0:
        return "total_not_positive"

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
            return "additional_charges_shape"
        city = re.fullmatch(
            r"City tax \(" + _MONEY + r" × ([1-9][0-9]?) guests? × "
            r"([1-9][0-9]?) nights?\) " + _MONEY,
            lines[price_index + 5],
        )
        final = re.fullmatch(_MONEY, lines[price_index + 8])
        if city is None or final is None:
            return "additional_charges_shape"
        rate_token, rate_text, party, duration, amount_token, amount = city.groups()
        if {_currency(rate_token), _currency(amount_token), _currency(final[1])} != {currency}:
            return "mixed_currency"
        rate = _amount(rate_text)
        additional_city = _amount(amount)
        final_total = _amount(final[2])
        if (
            int(party) != int(guests["adults"])
            or int(duration) != nights
            or rate <= 0
            or additional_city != rate * int(party) * int(duration)
            or final_total != total + additional_city
        ):
            return "additional_charges_arithmetic"
        qualified_notice_indexes = {price_index + 3, price_index + 4}
    elif any(line.rstrip(":").casefold() == "final price" for line in lines):
        return "unexpected_final_price"

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
        return "charge_warning"
    room_rows = [
        (i, re.fullmatch(r"1 (?:room|apartment) " + _MONEY, line))
        for i, line in enumerate(lines[:price_index])
    ]
    room_rows = [(i, match) for i, match in room_rows if match is not None]
    if len(room_rows) != 1:
        return "room_row"
    start, room_match = room_rows[0]
    assert room_match is not None
    if price_index - start > 4:
        return "room_row"
    if _currency(room_match[1]) != currency:
        return "mixed_currency"
    room_amount = _amount(room_match[2])
    charges = room_amount
    seen: set[str] = set()
    for line in lines[start + 1:price_index]:
        vat = re.fullmatch(r"([0-9]{1,2}(?:\.[0-9]{1,2})?) % (?:VAT|TAX) " + _MONEY, line)
        city = re.fullmatch(_MONEY + r" City tax per person per night " + _MONEY, line)
        if vat is not None and "vat" not in seen:
            rate, amount = Decimal(vat[1]), _amount(vat[3])
            expected = (room_amount * rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if _currency(vat[2]) != currency or amount != expected:
                return "tax_row"
            seen.add("vat")
        elif city is not None and "city" not in seen and not additional_city:
            rate, amount = _amount(city[2]), _amount(city[4])
            if {_currency(city[1]), _currency(city[3])} != {currency}:
                return "mixed_currency"
            if amount != rate * int(guests["adults"]) * nights:
                return "city_tax_row"
            seen.add("city")
        else:
            return "unrecognized_component_row"
        charges += amount
    if charges != total:
        return "components_do_not_sum"
    if statement_free and "vat" not in seen:
        return "tax_inclusion_unproven"
    # An unmatched monetary fee/tax row invalidates either layout, including rows below the
    # final-price statement. Only the additional layout has a reconciled row after its subtotal.
    recognized_rows = set(range(start, price_index))
    if additional_city:
        recognized_rows.add(price_index + 5)
    if any(
        index not in recognized_rows
        and re.search(_MONEY, line)
        and re.search(r"\b(?:tax(?:es)?|fees?|charges?)\b", line, re.I)
        for index, line in enumerate(lines)
    ):
        return "unreconciled_charge_row"
    return {"booked_total": str(final_total), "currency": currency, "all_in": "explicit"}


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
    payload.update(_meal_facts(lines, room is not None))
    for fact, outcome in (
        ("refundability", _cancellation_facts(lines, observed_at)),
        ("booked_total", _price_facts(lines, guests, nights)),
    ):
        if not isinstance(outcome, str):
            payload.update(outcome)
        elif reasons is not None:
            reasons[fact] = outcome
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
