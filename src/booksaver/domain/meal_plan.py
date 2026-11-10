from __future__ import annotations

from enum import Enum

MAX_MEAL_PLAN_TEXT = 200


class MealPlan(Enum):
    """What a rate includes, in ascending order of inclusion. UNKNOWN is never ranked."""

    NONE = "none"
    BREAKFAST = "breakfast"
    HALF_BOARD = "half_board"
    FULL_BOARD = "full_board"
    ALL_INCLUSIVE = "all_inclusive"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return _LABELS[self]

    def at_least(self, booked: MealPlan) -> bool:
        """Same or better than ``booked``. UNKNOWN is never ranked, on either side."""
        ranked = [plan for plan in MealPlan if plan is not MealPlan.UNKNOWN]
        return self in ranked and booked in ranked and ranked.index(self) >= ranked.index(booked)

    @classmethod
    def parse(cls, value: object) -> MealPlan:
        """Read a stored or submitted value; anything unrecognized is UNKNOWN."""
        try:
            return cls(value)
        except ValueError:
            return cls.UNKNOWN


_LABELS = {
    MealPlan.NONE: "no meals included",
    MealPlan.BREAKFAST: "breakfast included",
    MealPlan.HALF_BOARD: "half board (breakfast and dinner)",
    MealPlan.FULL_BOARD: "full board (breakfast, lunch and dinner)",
    MealPlan.ALL_INCLUSIVE: "all-inclusive",
    MealPlan.UNKNOWN: "meals not confirmed",
}
