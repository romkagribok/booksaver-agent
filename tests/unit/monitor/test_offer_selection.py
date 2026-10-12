from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from booksaver.domain.meal_plan import MealPlan
from booksaver.domain.offer import (
    ExclusionReason,
    OfferCandidate,
    select_offer,
)
from booksaver.domain.value_objects import Money

from .fakes import make_booking


def _candidate(
    label: str = "Standard Double",
    amount: str = "350.00",
    currency: str = "EUR",
    is_refundable: bool | None = True,
    matches_room: bool = True,
    confidence: float = 1.0,
) -> OfferCandidate:
    return OfferCandidate(
        room_label=label,
        total=Money(amount=Decimal(amount), currency=currency),
        is_refundable=is_refundable,
        cancellation_text="Free cancellation" if is_refundable else None,
        matches_room=matches_room,
        match_confidence=confidence,
    )


class TestExclusionRules:
    def test_non_refundable_excluded(self):
        selection = select_offer([_candidate(is_refundable=False)], make_booking())
        assert selection.chosen is None
        assert selection.excluded[0][1] is ExclusionReason.NOT_REFUNDABLE

    def test_unknown_refundability_excluded_not_guessed(self):
        selection = select_offer([_candidate(is_refundable=None)], make_booking())
        assert selection.chosen is None
        assert selection.excluded[0][1] is ExclusionReason.REFUNDABILITY_UNKNOWN

    def test_room_mismatch_excluded(self):
        selection = select_offer([_candidate(matches_room=False)], make_booking())
        assert selection.chosen is None
        assert selection.excluded[0][1] is ExclusionReason.ROOM_MISMATCH

    def test_low_confidence_match_excluded(self):
        selection = select_offer([_candidate(confidence=0.4)], make_booking())
        assert selection.chosen is None
        assert selection.excluded[0][1] is ExclusionReason.LOW_MATCH_CONFIDENCE

    def test_threshold_confidence_is_included(self):
        selection = select_offer([_candidate(confidence=0.5)], make_booking())
        assert selection.chosen is not None

    def test_currency_mismatch_excluded(self):
        selection = select_offer([_candidate(currency="USD")], make_booking())
        assert selection.chosen is None
        assert selection.excluded[0][1] is ExclusionReason.CURRENCY_MISMATCH
        assert selection.currency_mismatches == selection.excluded[0][:1]

    def test_only_otherwise_eligible_candidates_are_currency_mismatches(self):
        refundable = _candidate(currency="USD")
        not_refundable = _candidate(currency="USD", is_refundable=False)
        wrong_room = _candidate(currency="USD", matches_room=False)

        selection = select_offer(
            [refundable, not_refundable, wrong_room], make_booking()
        )

        assert selection.currency_mismatches == (refundable,)


class TestSelection:
    def test_cheapest_survivor_wins(self):
        candidates = [
            _candidate(amount="380.00"),
            _candidate(amount="340.00"),
            _candidate(amount="360.00"),
        ]
        selection = select_offer(candidates, make_booking())
        assert selection.chosen is not None
        assert selection.chosen.total.amount == Decimal("340.00")

    def test_cheaper_but_excluded_candidate_does_not_win(self):
        candidates = [
            _candidate(amount="200.00", is_refundable=False),
            _candidate(amount="360.00"),
        ]
        selection = select_offer(candidates, make_booking())
        assert selection.chosen is not None
        assert selection.chosen.total.amount == Decimal("360.00")

    def test_empty_candidate_list_selects_nothing(self):
        selection = select_offer([], make_booking())
        assert selection.chosen is None
        assert selection.excluded == ()

    def test_exclusion_summary_counts_reasons(self):
        candidates = [
            _candidate(is_refundable=False),
            _candidate(is_refundable=False),
            _candidate(matches_room=False),
        ]
        selection = select_offer(candidates, make_booking())
        summary = selection.exclusion_summary()
        assert "not_refundable=2" in summary
        assert "room_mismatch=1" in summary

    def test_exact_label_match_helper(self):
        booking = make_booking()  # room "Standard Double"
        assert _candidate(label="standard double ").exact_label_match(booking)
        assert not _candidate(label="Deluxe Double").exact_label_match(booking)


class TestMealPlanRule:
    """ADR-057: an offer is equivalent only with the same or a better meal plan."""

    @pytest.mark.parametrize(
        "booked, offered, expected",
        [
            # Only a reservation known to include meals constrains the offer.
            (MealPlan.UNKNOWN, MealPlan.NONE, None),
            (MealPlan.UNKNOWN, MealPlan.UNKNOWN, None),
            (MealPlan.NONE, MealPlan.NONE, None),
            (MealPlan.NONE, MealPlan.UNKNOWN, None),
            (MealPlan.NONE, MealPlan.BREAKFAST, None),
            (MealPlan.BREAKFAST, MealPlan.BREAKFAST, None),
            (MealPlan.BREAKFAST, MealPlan.HALF_BOARD, None),
            (MealPlan.HALF_BOARD, MealPlan.ALL_INCLUSIVE, None),
            (MealPlan.BREAKFAST, MealPlan.NONE, ExclusionReason.MEAL_PLAN_WORSE),
            (MealPlan.FULL_BOARD, MealPlan.HALF_BOARD, ExclusionReason.MEAL_PLAN_WORSE),
            (MealPlan.BREAKFAST, MealPlan.UNKNOWN, ExclusionReason.MEAL_PLAN_UNKNOWN),
        ],
    )
    def test_rule_table(self, booked, offered, expected):
        booking = replace(make_booking(), meal_plan=booked)
        candidate = replace(_candidate(), meal_plan=offered)
        selection = select_offer([candidate], booking)
        if expected is None:
            assert selection.chosen is candidate
        else:
            assert selection.chosen is None
            assert selection.excluded == ((candidate, expected),)

    def test_cheaper_room_only_rate_loses_to_the_breakfast_rate(self):
        # The reported defect: the same room, cheaper, without the booked breakfast.
        booking = replace(make_booking(), meal_plan=MealPlan.BREAKFAST)
        room_only = replace(_candidate(amount="300.00"), meal_plan=MealPlan.NONE)
        with_breakfast = replace(_candidate(amount="380.00"), meal_plan=MealPlan.BREAKFAST)
        selection = select_offer([room_only, with_breakfast], booking)
        assert selection.chosen is with_breakfast
        assert selection.exclusion_summary() == "meal_plan_worse=1"

    def test_currency_mismatch_only_counts_offers_that_also_satisfy_meals(self):
        booking = replace(make_booking(), meal_plan=MealPlan.BREAKFAST)
        room_only_usd = replace(_candidate(currency="USD"), meal_plan=MealPlan.NONE)
        selection = select_offer([room_only_usd], booking)
        assert selection.currency_mismatches == ()
        assert selection.excluded[0][1] is ExclusionReason.MEAL_PLAN_WORSE

    def test_earlier_rules_still_come_first(self):
        booking = replace(make_booking(), meal_plan=MealPlan.BREAKFAST)
        candidate = replace(_candidate(is_refundable=False), meal_plan=MealPlan.NONE)
        assert select_offer([candidate], booking).excluded[0][1] is ExclusionReason.NOT_REFUNDABLE
