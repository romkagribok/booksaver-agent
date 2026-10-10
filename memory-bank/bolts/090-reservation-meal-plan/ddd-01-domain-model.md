---
unit: 001-reservation-meal-plan
bolt: 090-reservation-meal-plan
stage: model
status: complete
created: "2026-10-10T02:02:11Z"
updated: "2026-10-10T07:49:45Z"
---

# Static Model - Reservation meal plan

Written after the code it describes (see the bolt's "Stage checkpoints").

## Bounded Context

Account synchronization: the facts BookSaver holds about a user's own Booking.com reservation.
The meal plan is one more fact of the reservation. Comparing it with offers belongs to the
savings context and to bolt 091.

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| Account reservation | existing facts plus `meal_plan`, `meal_plan_text` | The meal plan never affects eligibility for monitoring. |
| Booking (monitoring projection) | existing facts plus `meal_plan` | Mirrors the reservation's value; recording it does not invalidate a saved opportunity. |

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| MealPlan | `none`, `breakfast`, `half_board`, `full_board`, `all_inclusive`, `unknown` | Ascending order of inclusion; `unknown` is never ranked; each value has a plain-words label. |
| Booked meal plan | value plus the verbatim line it was read from | The line is at most 200 characters and empty when no line on the page stated the value. |

## Aggregates

| Aggregate Root | Members | Invariants |
|----------------|---------|------------|
| Account reservation | Booked meal plan | Only a code-owned reader sets it. A stated reading outranks the saved value, which outranks a reading from a page that stated nothing, which outranks `unknown`. |

## Domain Events

None. A changed meal plan raises the reservation's snapshot revision like any other changed fact.

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| Meal wording classification | `classify_meal_text(text) -> MealPlan`, `mentions_meals(text)` | None (pure). Shared with the offer side in bolt 091. |

Classification rules: an included value only for explicit inclusion wording; `none` only for
wording that denies a meal or prices a named meal as an extra; `unknown` for everything else,
including combinations outside the ranked values. Nothing is rounded to a neighbouring value.

## Repository Interfaces

| Repository | Entity | Methods |
|------------|--------|---------|
| Account reservation repository | Account reservation | `reconcile` stores the value and line and applies the precedence; `list_for_user` returns them. |
| Booking repository | Booking | Row mapping returns `meal_plan`. |

## Ubiquitous Language

| Term | Definition |
|------|------------|
| Meal plan | What a rate includes: nothing, breakfast, half board, full board, or all-inclusive. |
| Stated reading | A meal plan read from a line on the reservation page. |
| Silent reading | `none` inferred because a recognized room section said nothing about meals (owner decision). |
| Unknown | The page was not read, or its wording was not recognized. |
