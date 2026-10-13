---
unit: 002-meal-aware-offers
intent: 027-meal-plan-equivalence
phase: construction
status: complete
unit_type: backend
default_bolt_type: ddd-construction-bolt
created: "2026-10-10T01:49:45Z"
updated: "2026-10-10T07:49:45Z"
---

# Unit Brief: Meal-aware offers

## Purpose and scope

Read each candidate rate's meal plan on every price method that can produce an alert, gate
offer selection on it, and state both meal plans in alerts. Owns the amended repository
boundary in `AGENTS.md`.

## Assigned requirements

FR-1, FR-6, FR-7, FR-8, FR-9, FR-10. See ../../requirements.md.

## Domain concepts and operations

OfferMealPlan, meal exclusion reason, same-or-better comparison, alert meal statement.

## Stories

| Story | Title | Bolt |
|---|---|---|
| US-222 | Read each offer's meal plan | 091-meal-aware-offers |
| US-223 | Exclude offers with a worse meal plan | 091-meal-aware-offers |
| US-224 | State meal plans in savings alerts | 091-meal-aware-offers |
| US-225 | Apply the meal rule to every price method | 091-meal-aware-offers |

## Out of scope

Reading the reservation's meal plan (unit 001).

## Dependencies

Depends on unit 001's release and on a review of its production readings.
