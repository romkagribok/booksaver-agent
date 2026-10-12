---
unit: 002-meal-aware-offers
bolt: 091-meal-aware-offers
stage: model
status: complete
created: "2026-10-10T08:21:20Z"
updated: "2026-10-10T08:21:20Z"
---

# Static Model - Meal-aware offers

Written before any code for this bolt and without reading source files in this stage. It builds
on the investigation recorded in the intent's requirements and on bolt 090's model.

## Bounded Context

Savings evaluation: deciding whether a live offer is equivalent to the user's reservation and
cheaper. The price methods sit outside it and supply untrusted evidence about each rate. This
bolt adds one fact to that evidence, the rate's meal wording, and one rule to equivalence.

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| Observed offer (untrusted evidence from a price method) | existing facts plus `meal_text`: the rate's own wording about meals, the marker `none` when the rate shows nothing about meals, or `unknown` when the method could not tell | A price method never reports a meal plan value, only wording. Missing or unknown wording does not make the observation incomplete. |
| Candidate offer | existing facts plus `meal_plan` and the bounded `meal_plan_text` it was classified from | BookSaver classifies the wording with the classifier from bolt 090. `none` marker gives `none`; wording that does not classify gives `unknown`. |
| Check result | existing facts plus the chosen offer's `offer_meal_plan` | Recorded with every successful check so the alert and history can state it. |
| Savings opportunity | existing facts plus `offer_meal_plan` and the reservation's `booked_meal_plan` at validation | Both are frozen when the opportunity is validated. Rows saved before this bolt have neither. |

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| MealPlan (from bolt 090) | `none` < `breakfast` < `half_board` < `full_board` < `all_inclusive`; `unknown` | `unknown` is never ranked. |
| Meal exclusion reason | `meal_plan_worse`, `meal_plan_unknown` | Added to the existing exclusion reasons; visible in the check trace with counts. |
| Meal statement | reservation label, offer label, and whether the reservation's meal plan is confirmed | Rendered in plain words; the only form in which meal plans reach a user. |

## Aggregates

| Aggregate Root | Members | Invariants |
|----------------|---------|------------|
| Offer selection | candidate offers, exclusions with reasons, the chosen offer | See the rule below. The chosen offer is the cheapest survivor. An offer excluded only for its rendered currency must already satisfy every other rule, including meals. |

### The meal rule

| Reservation's meal plan | Offer's meal plan | Result |
|-------------------------|-------------------|--------|
| `unknown` | anything | not excluded on meals (the alert carries a caveat) |
| `none` | anything, including `unknown` | not excluded on meals |
| includes meals | `unknown` | excluded, `meal_plan_unknown` |
| includes meals | ranks lower | excluded, `meal_plan_worse` |
| includes meals | same or higher | not excluded on meals |

Order of evaluation for one candidate: refundability, room, match confidence, meals, currency.

## Domain Events

| Event | Trigger | Payload |
|-------|---------|---------|
| No equivalent offer (existing conclusive observation) | every candidate that passed the earlier rules was excluded on meals | counts per exclusion reason. As intent 018 already defines for this observation, it leaves the booking with no current opportunity and deletes no history. It is not a technical failure and raises no incident. |
| Savings opportunity validated (existing) | a surviving offer is cheaper than the baseline | now also carries both meal plans |

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| Meal wording classification (bolt 090) | `classify_meal_text` | none |
| Offer selection | applies the meal rule | the booking's recorded meal plan |
| Savings detection | copies the chosen offer's meal plan and the booking's into the opportunity | check result, booking |
| Alert composition | builds the meal statement | opportunity, booking |

## Repository Interfaces

| Repository | Entity | Methods |
|------------|--------|---------|
| Check history | Check result | save and load `offer_meal_plan` |
| Savings opportunities | Savings opportunity | save and load `offer_meal_plan`, `booked_meal_plan` |

## Ubiquitous Language

| Term | Definition |
|------|------------|
| Meal wording | What a rate row itself says about meals, verbatim. |
| Nothing stated | The rate row shows no meal wording. For an offer this means no meals. |
| Same or better | The offer's meal plan ranks at or above the reservation's. |
| Meal caveat | The sentence used when the reservation's own meal plan is `unknown`. |

## Story coverage

- US-222: observed offer, candidate offer, classification.
- US-223: the meal rule, exclusion reasons, the conclusive no-equivalent-offer observation.
- US-224: check result and opportunity carry the meal plans; meal statement and caveat. The
  re-evaluation criterion is met by the existing lifecycle: the next conclusive check replaces or
  clears the current opportunity.
- US-225: every price method produces the same observed-offer shape and passes the same selection.
