from __future__ import annotations

import re
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

_MEALS = ("breakfast", "lunch", "dinner")
_MEAL_WORDS = re.compile(
    r"\b(?:breakfast|lunch|dinner|meals?|half[- ]board|full[- ]board|all[- ]inclusive|room only)\b",
    re.IGNORECASE,
)
_CLAUSES = re.compile(r"[.;!•|\n]+")
_NEGATED = re.compile(
    r"\bno meals?\b|\bno (?:breakfast|lunch|dinner)\b|\broom only\b|\bwithout\b"
    r"|\bexclud(?:e|es|ed|ing)\b|\bnot\b|\bisn't\b|\baren't\b"
)
# A meal offered at a price is an optional extra, not an inclusion.
_EXTRA = re.compile(
    r"\bcosts?\b|\boptional\b|\bextra\b|\badditional\b|\bsurcharge\b|\bsupplement\b"
    r"|\bfor just\b|\badd\b|\bpurchase\b"
)
# An amount with its currency. A bare number is a time or a guest count, not a price.
_CURRENCY = (
    r"(?:[$\u20ac\u00a3\u00a5\u20b9\u20bd\u20ba\u20b4\u20a9\u20aa\u0e3f]|\b(?:usd|eur|gbp|chf|cad|aud|nzd|jpy|cny"
    r"|sek|nok|dkk|pln|czk|huf|ron|bgn|rub|uah|ils|aed|inr|thb|sgd|hkd|mxn|brl|zar|krw)\b)"
)
_PRICE = re.compile(rf"{_CURRENCY}\s?[0-9]|[0-9]\s?{_CURRENCY}")
_INCLUDED = re.compile(r"\binclud(?:ed|es|ing)\b|\bcomplimentary\b")
_ALL_INCLUSIVE = re.compile(r"\ball[- ]inclusive\b")
_FULL_BOARD = re.compile(r"\bfull[- ]board\b")
_HALF_BOARD = re.compile(r"\bhalf[- ]board\b")
_BY_MEALS = {
    frozenset({"breakfast"}): MealPlan.BREAKFAST,
    frozenset({"breakfast", "dinner"}): MealPlan.HALF_BOARD,
    frozenset({"breakfast", "lunch", "dinner"}): MealPlan.FULL_BOARD,
}


def mentions_meals(text: str) -> bool:
    return _MEAL_WORDS.search(text) is not None


def classify_meal_text(text: str) -> MealPlan:
    """Classify Booking.com wording about what a rate includes.

    Returns NONE only for wording that denies a meal or offers a named meal at a price or as extra,
    an included value only for explicit inclusion wording, and UNKNOWN for everything else,
    including meal combinations outside the ranked values. Nothing is rounded to a neighbour.
    """
    included: set[str] = set()
    plans: set[MealPlan] = set()
    stated_none = False
    unrecognized = False
    for raw in _CLAUSES.split(text.casefold().replace("\u2019", "'")):
        clause = " ".join(raw.split())
        if not clause or not mentions_meals(clause):
            continue
        named = None
        if _ALL_INCLUSIVE.search(clause):
            named = MealPlan.ALL_INCLUSIVE
        elif _FULL_BOARD.search(clause):
            named = MealPlan.FULL_BOARD
        elif _HALF_BOARD.search(clause):
            named = MealPlan.HALF_BOARD
        meals = {meal for meal in _MEALS if re.search(rf"\b{meal}\b", clause)}
        extra = _EXTRA.search(clause) is not None
        positive = named is not None or (bool(meals) and _INCLUDED.search(clause) is not None)
        if _NEGATED.search(clause) is not None:
            # One clause that both denies and names several meals is a mixed statement.
            if named is not None or len(meals) > 1:
                unrecognized = True
            else:
                stated_none = True
        elif positive and extra:
            unrecognized = True
        elif named is not None:
            plans.add(named)
        elif positive:
            included |= meals
        elif meals and (extra or _PRICE.search(clause) is not None):
            stated_none = True
        else:
            unrecognized = True
    if included:
        by_meals = _BY_MEALS.get(frozenset(included))
        if by_meals is None:
            return MealPlan.UNKNOWN
        plans.add(by_meals)
    if unrecognized or len(plans) > 1:
        return MealPlan.UNKNOWN
    if plans:
        return next(iter(plans))
    return MealPlan.NONE if stated_none else MealPlan.UNKNOWN
