from __future__ import annotations

import json
import logging
from typing import Any

from booksaver.application.ports import ExtractionResult
from booksaver.domain.models import Booking
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
