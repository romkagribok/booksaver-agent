---
unit: 001-reservation-meal-plan
intent: 027-meal-plan-equivalence
phase: construction
status: in-progress
unit_type: backend
default_bolt_type: ddd-construction-bolt
created: "2026-10-10T01:49:45Z"
updated: "2026-10-10T07:49:45Z"
---

# Unit Brief: Reservation meal plan

## Purpose and scope

Read, store, and show each reservation's meal plan. Owns the meal plan value and its text
classifier in the domain layer, the confirmation parser rule, the path from observed
reservation to `account_reservations` and `bookings` (schema v21), and the `/bookings` line.

## Assigned requirements

FR-2, FR-3, FR-4, FR-5. See ../../requirements.md.

## Domain concepts and operations

MealPlan, BookedMealPlan (value plus verbatim line), meal wording classification, reading
precedence across synchronizations.

## Stories

| Story | Title | Bolt |
|---|---|---|
| US-220 | Record the reservation's meal plan | 090-reservation-meal-plan |
| US-221 | Show the meal plan in /bookings | 090-reservation-meal-plan |

## Out of scope

Offer selection, alerts and every price method.

## Dependencies

None on other units. Unit 002 depends on this unit's stored meal plan.
