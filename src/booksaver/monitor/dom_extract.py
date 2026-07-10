from __future__ import annotations

import re

from booksaver.application.ports import ExtractionResult
from booksaver.domain.value_objects import Money

# Best-effort DOM/text extraction. Booking.com's layout changes frequently, so this
# targets stable text patterns rather than CSS classes; the LLM fallback (US-006)
# is the robust path when these patterns miss.

_CURRENCY_SYMBOLS = {
    "€": "EUR",
    "$": "USD",
    "£": "GBP",
}

# e.g. "€ 1,234.56", "EUR 1234.56", "1.234,56 €"
_PRICE_PATTERNS = [
    re.compile(r"(?P<cur>€|\$|£)\s?(?P<amt>\d{1,3}(?:[,.]\d{3})*(?:[,.]\d{2})?)"),
    re.compile(r"(?P<cur>EUR|USD|GBP)\s?(?P<amt>\d{1,3}(?:[,.]\d{3})*(?:[,.]\d{2})?)"),
    re.compile(r"(?P<amt>\d{1,3}(?:[,.]\d{3})*(?:[,.]\d{2})?)\s?(?P<cur>€|\$|£|EUR|USD|GBP)"),
]

# Contexts that suggest the matched price is the reservation total, not an ad or upsell
_TOTAL_HINTS = re.compile(r"(total price|total|final price|you(?:'| wi)ll pay)", re.IGNORECASE)

_REFUNDABLE_HINTS = re.compile(
    r"(free cancellation|fully refundable|refundable until|cancel for free)", re.IGNORECASE
)
_NON_REFUNDABLE_HINTS = re.compile(r"(non-?refundable|no refund)", re.IGNORECASE)


def _normalise_amount(raw: str) -> str:
    """Convert '1.234,56' / '1,234.56' / '1234' to a canonical '1234.56' string."""
    raw = raw.strip()
    if "," in raw and "." in raw:
        if raw.rindex(",") > raw.rindex("."):
            # European style: 1.234,56
            raw = raw.replace(".", "").replace(",", ".")
        else:
            # US style: 1,234.56
            raw = raw.replace(",", "")
    elif "," in raw:
        # Trailing ,xx is decimals; otherwise thousands
        head, _, tail = raw.rpartition(",")
        raw = f"{head.replace(',', '')}.{tail}" if len(tail) == 2 else raw.replace(",", "")
    return raw


def extract_from_text(text: str) -> ExtractionResult:
    """Scan page text for a total price near a 'total' hint, plus refund indicators."""
    best: tuple[str, str] | None = None  # (amount, currency)
    for line in text.splitlines():
        if not _TOTAL_HINTS.search(line):
            continue
        for pattern in _PRICE_PATTERNS:
            m = pattern.search(line)
            if m:
                cur = m.group("cur")
                currency = _CURRENCY_SYMBOLS.get(cur, cur)
                best = (_normalise_amount(m.group("amt")), currency)
                break
        if best:
            break

    is_refundable: bool | None = None
    if _NON_REFUNDABLE_HINTS.search(text):
        is_refundable = False
    elif _REFUNDABLE_HINTS.search(text):
        is_refundable = True

    if best is None:
        return ExtractionResult(
            price=None,
            is_refundable=is_refundable,
            cancellation_deadline_raw=None,
            confidence=0.0,
        )

    try:
        price = Money.of(best[0], best[1])
    except ValueError:
        return ExtractionResult(
            price=None,
            is_refundable=is_refundable,
            cancellation_deadline_raw=None,
            confidence=0.0,
        )

    return ExtractionResult(
        price=price,
        is_refundable=is_refundable,
        cancellation_deadline_raw=None,
        confidence=0.8,
    )
