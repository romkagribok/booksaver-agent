from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import Booking
from .value_objects import Money

MATCH_CONFIDENCE_THRESHOLD = 0.5


class ExclusionReason(Enum):
    NOT_REFUNDABLE = "not_refundable"
    REFUNDABILITY_UNKNOWN = "refundability_unknown"
    ROOM_MISMATCH = "room_mismatch"
    LOW_MATCH_CONFIDENCE = "low_match_confidence"
    CURRENCY_MISMATCH = "currency_mismatch"


@dataclass(frozen=True)
class OfferCandidate:
    """One row of the property page's room/rate table, as a bookable offer.

    ``total`` is the all-in bookable total as displayed (including shown
    taxes/charges) — the figure a rebooking customer would pay.
    """

    room_label: str
    total: Money
    is_refundable: bool | None
    cancellation_text: str | None
    matches_room: bool
    match_confidence: float

    def exact_label_match(self, booking: Booking) -> bool:
        return self.room_label.strip().lower() == booking.room_type.label.strip().lower()


@dataclass(frozen=True)
class OfferSelection:
    chosen: OfferCandidate | None
    excluded: tuple[tuple[OfferCandidate, ExclusionReason], ...]

    @property
    def currency_mismatches(self) -> tuple[OfferCandidate, ...]:
        """Otherwise-eligible offers rejected only for rendered currency."""
        return tuple(
            candidate
            for candidate, reason in self.excluded
            if reason is ExclusionReason.CURRENCY_MISMATCH
        )

    def exclusion_summary(self) -> str:
        counts: dict[str, int] = {}
        for _, reason in self.excluded:
            counts[reason.value] = counts.get(reason.value, 0) + 1
        return ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none"


def _exclusion_for(candidate: OfferCandidate, booking: Booking) -> ExclusionReason | None:
    # Refundability must be positively evidenced — absence rejects (mirrors US-008).
    if candidate.is_refundable is None:
        return ExclusionReason.REFUNDABILITY_UNKNOWN
    if candidate.is_refundable is False:
        return ExclusionReason.NOT_REFUNDABLE
    if not candidate.matches_room:
        return ExclusionReason.ROOM_MISMATCH
    if candidate.match_confidence < MATCH_CONFIDENCE_THRESHOLD:
        return ExclusionReason.LOW_MATCH_CONFIDENCE
    if candidate.total.currency != booking.baseline_price.currency:
        return ExclusionReason.CURRENCY_MISMATCH
    return None


def select_offer(candidates: list[OfferCandidate], booking: Booking) -> OfferSelection:
    """US-019 selection: cheapest equivalent, still-refundable candidate or nothing.

    Low confidence and unknown refundability are exclusions, never guesses — an
    empty selection becomes a NO_EQUIVALENT_OFFER check failure upstream.
    """
    excluded: list[tuple[OfferCandidate, ExclusionReason]] = []
    surviving: list[OfferCandidate] = []
    for candidate in candidates:
        reason = _exclusion_for(candidate, booking)
        if reason is None:
            surviving.append(candidate)
        else:
            excluded.append((candidate, reason))

    chosen = min(surviving, key=lambda c: c.total.amount) if surviving else None
    return OfferSelection(chosen=chosen, excluded=tuple(excluded))
