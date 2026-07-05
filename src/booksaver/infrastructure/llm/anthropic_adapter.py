from __future__ import annotations

import json
import logging
from typing import Any

from booksaver.application.ports import ExtractionResult
from booksaver.domain.models import Booking
from booksaver.domain.offer import OfferCandidate
from booksaver.domain.value_objects import Money

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5"

_MAX_PAGE_CHARS = 30_000  # keep prompts bounded; manage pages are text-heavy

_EXTRACTION_PROMPT = """\
You are extracting reservation pricing data from the visible text of a Booking.com
manage-booking page. The user's reservation:

- Property: {property_name}
- Room: {room_type}
- Check-in: {check_in}
- Check-out: {check_out}

From the page text below, extract the CURRENT TOTAL PRICE for this reservation
(or for rebooking the equivalent room on the same dates, if shown), plus
cancellation-policy indicators.

Respond with ONLY a JSON object, no other text:
{{"price": "<decimal string or null>", "currency": "<ISO-4217 code or null>",
"is_refundable": <true/false/null>, "cancellation_deadline": "<text or null>",
"confidence": <0.0-1.0>}}

Page text:
---
{page_text}
---"""

_OFFERS_PROMPT = """\
You are reading the visible text of a Booking.com PROPERTY PAGE room/rate table.
The user's existing reservation (they are looking for a cheaper equivalent):

- Property: {property_name}
- Room booked: {room_type}
- Check-in: {check_in}
- Check-out: {check_out}
- Party: {adults} adults, {children} children, {rooms} room(s)

List every bookable offer (room + rate) shown in the page text. For each offer report
the TOTAL price for the whole stay as displayed (including shown taxes/charges), whether
the rate is refundable/free-cancellation (null if the text doesn't say), and whether the
room is the same room type the user booked. "matches_room" must be a strict judgment:
true only if it is the same room type (naming variations like "Standard Double Room" vs
"Double Room" may match); different bed setup, different capacity, or upgraded categories
do NOT match. Express your certainty in match_confidence (0.0-1.0).

Respond with ONLY a JSON array, no other text:
[{{"room_label": "<string>", "price": "<decimal string>", "currency": "<ISO-4217>",
"is_refundable": <true/false/null>, "cancellation_text": "<string or null>",
"matches_room": <true/false>, "match_confidence": <0.0-1.0>}}]

Page text:
---
{page_text}
---"""


class AnthropicExtractor:
    """LLMExtractor adapter over the official Anthropic SDK (ADR-009).

    The SDK is imported lazily; construction fails cleanly if it is missing.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def extract_price(self, page_text: str, booking: Booking) -> ExtractionResult:
        prompt = _EXTRACTION_PROMPT.format(
            property_name=booking.property.name,
            room_type=booking.room_type.label,
            check_in=booking.stay_dates.check_in.isoformat(),
            check_out=booking.stay_dates.check_out.isoformat(),
            page_text=page_text[:_MAX_PAGE_CHARS],
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        from anthropic.types import TextBlock

        raw = "".join(
            block.text for block in response.content if isinstance(block, TextBlock)
        )
        return parse_extraction_response(raw)

    def extract_offers(self, page_text: str, booking: Booking) -> list[OfferCandidate]:
        occ = booking.occupancy
        prompt = _OFFERS_PROMPT.format(
            property_name=booking.property.name,
            room_type=booking.room_type.label,
            check_in=booking.stay_dates.check_in.isoformat(),
            check_out=booking.stay_dates.check_out.isoformat(),
            adults=occ.adults if occ else "?",
            children=occ.children if occ else "?",
            rooms=occ.rooms if occ else "?",
            page_text=page_text[:_MAX_PAGE_CHARS],
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        from anthropic.types import TextBlock

        raw = "".join(
            block.text for block in response.content if isinstance(block, TextBlock)
        )
        return parse_offers_response(raw)


def parse_extraction_response(raw: str) -> ExtractionResult:
    """Parse the model's JSON reply; malformed replies yield a zero-confidence result."""
    empty = ExtractionResult(
        price=None, is_refundable=None, cancellation_deadline_raw=None, confidence=0.0
    )

    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        logger.warning("LLM reply contained no JSON object")
        return empty

    try:
        data: dict[str, Any] = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        logger.warning("LLM reply was not valid JSON")
        return empty

    price: Money | None = None
    if data.get("price") and data.get("currency"):
        try:
            price = Money.of(str(data["price"]), str(data["currency"]))
        except ValueError:
            logger.warning("LLM returned unparseable price: %r %r", data["price"], data["currency"])

    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
        confidence = 0.0 if price is None else 0.5

    is_refundable = data.get("is_refundable")
    if not isinstance(is_refundable, bool):
        is_refundable = None

    deadline = data.get("cancellation_deadline")
    if deadline is not None and not isinstance(deadline, str):
        deadline = None

    return ExtractionResult(
        price=price,
        is_refundable=is_refundable,
        cancellation_deadline_raw=deadline,
        confidence=float(confidence),
    )


def parse_offers_response(raw: str) -> list[OfferCandidate]:
    """Parse the model's JSON array of offers; malformed replies yield an empty list
    (which upstream treats as extraction failure, never a guessed savings signal)."""
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        logger.warning("LLM offers reply contained no JSON array")
        return []

    try:
        items = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        logger.warning("LLM offers reply was not valid JSON")
        return []
    if not isinstance(items, list):
        return []

    candidates: list[OfferCandidate] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            total = Money.of(str(item["price"]), str(item["currency"]))
        except (KeyError, ValueError):
            logger.warning("Skipping offer with unparseable price: %r", item)
            continue
        label = item.get("room_label")
        if not isinstance(label, str) or not label.strip():
            continue

        is_refundable = item.get("is_refundable")
        if not isinstance(is_refundable, bool):
            is_refundable = None
        cancellation = item.get("cancellation_text")
        if cancellation is not None and not isinstance(cancellation, str):
            cancellation = None
        confidence = item.get("match_confidence")
        if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
            confidence = 0.0

        candidates.append(
            OfferCandidate(
                room_label=label.strip(),
                total=total,
                is_refundable=is_refundable,
                cancellation_text=cancellation,
                matches_room=bool(item.get("matches_room")),
                match_confidence=float(confidence),
            )
        )
    return candidates
