import pytest

from booksaver.domain.meal_plan import (
    MealPlan,
    classify_meal_text,
    mentions_meals,
    offer_meal_plan,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        # Wording from the owner's reservation examples.
        ("No meal is included in this room rate.", MealPlan.NONE),
        ("Breakfast included", MealPlan.BREAKFAST),
        ("Breakfast is included in the room rate.", MealPlan.BREAKFAST),
        ("Breakfast is included in the room rate for 2 guests", MealPlan.BREAKFAST),
        ("Very good breakfast included", MealPlan.BREAKFAST),
        ("Breakfast & dinner included", MealPlan.HALF_BOARD),
        ("Half board", MealPlan.HALF_BOARD),
        ("Breakfast, lunch and dinner are included", MealPlan.FULL_BOARD),
        ("Full-board", MealPlan.FULL_BOARD),
        ("All-inclusive", MealPlan.ALL_INCLUSIVE),
        ("There is no meal option with this room.", MealPlan.NONE),
        ("Breakfast isn’t included", MealPlan.NONE),
        ("Room only", MealPlan.NONE),
        # A priced meal is an optional extra, not an inclusion.
        ("Breakfast costs € 15 per person per night.", MealPlan.NONE),
        ("Breakfast US$20 (optional)", MealPlan.NONE),
        ("Add breakfast for € 12", MealPlan.NONE),
        ("Breakfast 20 EUR", MealPlan.NONE),
        ("Breakfast excluded", MealPlan.NONE),
        ("Excluding breakfast", MealPlan.NONE),
        (
            "Breakfast is included in the room rate. Dinner costs €20 per person.",
            MealPlan.BREAKFAST,
        ),
        # Never rounded to a neighbouring value.
        ("Breakfast & lunch included", MealPlan.UNKNOWN),
        ("Dinner included", MealPlan.UNKNOWN),
        ("Breakfast included, lunch not included", MealPlan.UNKNOWN),
        ("Breakfast included, dinner optional", MealPlan.UNKNOWN),
        ("Half board. All-inclusive", MealPlan.UNKNOWN),
        # "Exclusive" is not a denial, and a bare number is a time or a guest count, not a price.
        ("Exclusive breakfast included", MealPlan.BREAKFAST),
        ("Breakfast included for 2 guests from 7:00", MealPlan.BREAKFAST),
        ("Exclusive breakfast", MealPlan.UNKNOWN),
        ("Breakfast 7:00-10:00", MealPlan.UNKNOWN),
        ("Breakfast for 2 guests", MealPlan.UNKNOWN),
        ("Breakfast available", MealPlan.UNKNOWN),
        ("Breakfast per person", MealPlan.UNKNOWN),
        ("Breakfast", MealPlan.UNKNOWN),
        ("Meals", MealPlan.UNKNOWN),
        # A number or price without a named meal says nothing about what is included.
        ("2 meals per day", MealPlan.UNKNOWN),
        ("Meals available at extra cost", MealPlan.UNKNOWN),
        ("Standard Double Room", MealPlan.UNKNOWN),
        ("", MealPlan.UNKNOWN),
    ],
)
def test_classifies_booking_meal_wording(text: str, expected: MealPlan) -> None:
    assert classify_meal_text(text) is expected


def test_mentions_meals_ignores_unrelated_room_text() -> None:
    assert mentions_meals("Very good breakfast included")
    assert not mentions_meals("Private bathroom, Dining table, Desk")


def test_stored_values_parse_and_anything_else_is_unknown() -> None:
    assert MealPlan.parse("half_board") is MealPlan.HALF_BOARD
    assert MealPlan.parse(None) is MealPlan.UNKNOWN
    assert MealPlan.parse("brunch") is MealPlan.UNKNOWN
    assert MealPlan.UNKNOWN.label == "meals not confirmed"


@pytest.mark.parametrize(
    "meal_text, expected",
    [
        ("none", MealPlan.NONE),
        (" None ", MealPlan.NONE),
        ("Breakfast included", MealPlan.BREAKFAST),
        ("Very good breakfast included\nDinner US$30", MealPlan.BREAKFAST),
        ("Breakfast US$15", MealPlan.NONE),
        # Anything a price method could not ground can only exclude the offer.
        (None, MealPlan.UNKNOWN),
        ("", MealPlan.UNKNOWN),
        ("unknown", MealPlan.UNKNOWN),
        ("Free WiFi", MealPlan.UNKNOWN),
        ("Breakfast", MealPlan.UNKNOWN),
    ],
)
def test_offer_wording_is_classified_by_code(meal_text: str | None, expected: MealPlan) -> None:
    assert offer_meal_plan(meal_text) is expected


def test_same_or_better_never_ranks_unknown() -> None:
    assert MealPlan.HALF_BOARD.at_least(MealPlan.BREAKFAST)
    assert MealPlan.BREAKFAST.at_least(MealPlan.BREAKFAST)
    assert not MealPlan.NONE.at_least(MealPlan.BREAKFAST)
    assert not MealPlan.UNKNOWN.at_least(MealPlan.NONE)
    assert not MealPlan.ALL_INCLUSIVE.at_least(MealPlan.UNKNOWN)
