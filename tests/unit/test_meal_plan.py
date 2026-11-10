from booksaver.domain.meal_plan import MealPlan


def test_stored_values_parse_and_anything_else_is_unknown() -> None:
    assert MealPlan.parse("half_board") is MealPlan.HALF_BOARD
    assert MealPlan.parse(None) is MealPlan.UNKNOWN
    assert MealPlan.parse("brunch") is MealPlan.UNKNOWN
    assert MealPlan.UNKNOWN.label == "meals not confirmed"


def test_same_or_better_never_ranks_unknown() -> None:
    assert MealPlan.HALF_BOARD.at_least(MealPlan.BREAKFAST)
    assert MealPlan.BREAKFAST.at_least(MealPlan.BREAKFAST)
    assert not MealPlan.NONE.at_least(MealPlan.BREAKFAST)
    assert not MealPlan.UNKNOWN.at_least(MealPlan.NONE)
    assert not MealPlan.ALL_INCLUSIVE.at_least(MealPlan.UNKNOWN)
