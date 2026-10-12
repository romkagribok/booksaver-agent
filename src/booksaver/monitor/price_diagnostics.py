"""Content-minimized explanations of the decisions BookSaver actually made."""

import re
from collections import Counter
from collections.abc import Callable, Sequence

from booksaver.application.browser_executor import PriceExecutionOutcome
from booksaver.domain.browser_executor import observed_offer_rejection_reasons
from booksaver.domain.models import Booking
from booksaver.domain.offer import OfferCandidate, OfferSelection

MAX_DIAGNOSTIC_OFFERS = 20
# Lexical hints only. Never infer absence, synonyms, or room equivalence from these words.
_ROOM_WORDS = frozenset(
    "standard deluxe superior executive premium economy classic king queen twin double single "
    "suite studio apartment room bedroom bed beds accessible accessibility hearing mobility "
    "balcony terrace ocean sea garden city mountain view sofa smoking nonsmoking breakfast "
    "refundable flexible cancellation one two three four".split()
)


def _room_hints(label: str) -> dict[str, object]:
    words = re.findall(r"[a-z]+", label.casefold())
    return {
        "recognized_words": sorted(set(words) & _ROOM_WORDS),
        "other_word_count": sum(word not in _ROOM_WORDS for word in words),
    }


def price_validation_diagnostics(
    booking: Booking,
    outcome: PriceExecutionOutcome,
    candidates: Sequence[OfferCandidate],
    selection: OfferSelection | None,
    normalize_room: Callable[[str], str],
) -> dict[str, object]:
    """Project only closed codes, booleans, counts, and allowlisted vocabulary."""
    booked = " ".join(booking.room_type.label.casefold().split())
    offers = outcome.result.offers
    records: list[dict[str, object]] = []
    candidate_index = 0
    for index, offer in enumerate(offers[:MAX_DIAGNOSTIC_OFFERS]):
        reasons = observed_offer_rejection_reasons(offer, booking.baseline_price.currency)
        observed = " ".join(offer.room_label.casefold().split())
        record: dict[str, object] = {
            "offer_index": index,
            "evidence_rejections": list(reasons),
            "completeness": offer.completeness.value,
            "all_in": offer.all_in.value,
            "refundability": offer.refundability.value,
            "refundability_text_present": offer.refundability_text is not None,
            "currency_matches": offer.total.currency == booking.baseline_price.currency,
            "observed_room_hints": _room_hints(offer.room_label),
            "normalized_label_equal": observed == booked,
            "same_word_multiset": Counter(re.findall(r"\w+", observed))
            == Counter(re.findall(r"\w+", booked)),
            "same_identity_after_both_suffixes": normalize_room(offer.room_label)
            == normalize_room(booking.room_type.label),
            "observed_suffix_removed": normalize_room(offer.room_label) != observed,
            "booked_suffix_present": normalize_room(booking.room_type.label) != booked,
            "room_comparison": "not_evaluated",
            "selection": "not_evaluated",
        }
        if not reasons and outcome.validation.accepted and candidate_index < len(candidates):
            candidate = candidates[candidate_index]
            candidate_index += 1
            record["room_comparison"] = "matched" if candidate.matches_room else "mismatched"
            record["meal_plan"] = candidate.meal_plan.value
            if selection is not None:
                excluded = next(
                    (reason.value for item, reason in selection.excluded if item is candidate), None
                )
                record["selection"] = (
                    excluded
                    or ("selected" if selection.chosen is candidate else "eligible_not_selected")
                )
        records.append(record)
    return {
        "version": "price-validation-v1",
        "executor_status": outcome.result.status.value,
        "query_or_evidence_rejection": (
            outcome.validation.rejection.value if outcome.validation.rejection else None
        ),
        "observed_offer_count": len(offers),
        "evidence_accepted_count": len(outcome.validation.accepted_offers),
        "evidence_rejected_count": outcome.validation.rejected_offer_count,
        "observed_evidence_reason_counts": dict(Counter(
            reason for offer in offers
            for reason in observed_offer_rejection_reasons(offer, booking.baseline_price.currency)
        )),
        "room_evaluated_count": len(candidates),
        "room_matched_count": sum(item.matches_room for item in candidates),
        "selected": selection is not None and selection.chosen is not None,
        "booked_room_hints": _room_hints(booking.room_type.label),
        "offers": records,
        "omitted_offer_count": max(0, len(offers) - MAX_DIAGNOSTIC_OFFERS),
    }
