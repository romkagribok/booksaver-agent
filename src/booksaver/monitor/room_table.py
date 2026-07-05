from __future__ import annotations

import re

from booksaver.domain.models import Booking
from booksaver.domain.offer import OfferCandidate
from booksaver.domain.value_objects import Money

from .dom_extract import _CURRENCY_SYMBOLS, _PRICE_PATTERNS, _normalise_amount

# Best-effort room-table parsing from the property page's visible text. Like
# dom_extract, this targets stable text patterns, not CSS classes; the LLM
# extract_offers call (US-019) is the robust path when these patterns miss.

_REFUNDABLE_HINTS = re.compile(
    r"(free cancellation|fully refundable|refundable until|cancel for free)", re.IGNORECASE
)
_NON_REFUNDABLE_HINTS = re.compile(r"(non-?refundable|no refund)", re.IGNORECASE)

# Lines that look like room names: contain a room-ish word and aren't price/policy lines
_ROOM_WORDS = re.compile(
    r"\b(room|suite|studio|apartment|double|twin|single|king|queen|deluxe|superior|"
    r"standard|family|dormitory)\b",
    re.IGNORECASE,
)


def _find_price(line: str) -> Money | None:
    for pattern in _PRICE_PATTERNS:
        m = pattern.search(line)
        if m:
            cur = m.group("cur")
            currency = _CURRENCY_SYMBOLS.get(cur, cur)
            try:
                return Money.of(_normalise_amount(m.group("amt")), currency)
            except ValueError:
                return None
    return None


def parse_candidates(text: str, booking: Booking) -> list[OfferCandidate]:
    """Scan property-page text for room blocks: a room-name line followed (within a
    few lines) by a price and cancellation-policy wording.

    Only *exact* label matches are marked ``matches_room`` here — naming drift is
    the LLM's judgment call, never this parser's.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    wanted = booking.room_type.label.strip().lower()
    candidates: list[OfferCandidate] = []

    for i, line in enumerate(lines):
        if not _ROOM_WORDS.search(line) or _find_price(line) is not None:
            continue
        label = line
        window = lines[i + 1 : i + 8]

        price: Money | None = None
        is_refundable: bool | None = None
        cancellation_text: str | None = None
        for w in window:
            if _ROOM_WORDS.search(w) and _find_price(w) is None:
                break  # next room block started
            if price is None:
                price = _find_price(w)
            if _NON_REFUNDABLE_HINTS.search(w):
                is_refundable = False
                cancellation_text = w
            elif is_refundable is None and _REFUNDABLE_HINTS.search(w):
                is_refundable = True
                cancellation_text = w

        if price is None:
            continue
        exact = label.strip().lower() == wanted
        candidates.append(
            OfferCandidate(
                room_label=label,
                total=price,
                is_refundable=is_refundable,
                cancellation_text=cancellation_text,
                matches_room=exact,
                match_confidence=1.0 if exact else 0.0,
            )
        )
    return candidates


def has_confident_exact_match(candidates: list[OfferCandidate], booking: Booking) -> bool:
    """True when DOM parsing alone found the booked room with explicit refundability —
    the zero-LLM-call happy path."""
    return any(
        c.exact_label_match(booking) and c.is_refundable is not None for c in candidates
    )
