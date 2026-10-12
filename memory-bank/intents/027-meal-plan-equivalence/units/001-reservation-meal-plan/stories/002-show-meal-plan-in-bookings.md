---
id: 002-show-meal-plan-in-bookings
unit: 001-reservation-meal-plan
intent: 027-meal-plan-equivalence
status: complete
priority: must
created: "2026-10-10T01:49:45Z"
assigned_bolt: 090-reservation-meal-plan
implemented: true
---

# US-221: Show the meal plan in /bookings

## User story

As a BookSaver user, I want `/bookings` to show the meal plan recorded for each reservation,
so that I can spot a wrong reading.

## Assigned requirement

FR-5.

## Acceptance criteria

- [ ] Given a reservation with a recorded meal plan, when `/bookings` lists it, then the entry
  shows the meal plan in plain words.
- [ ] Given a reservation whose meal plan is `unknown`, when `/bookings` lists it, then the entry
  says "meals not confirmed".
- [ ] Given the stored verbatim wording, when `/bookings` lists the reservation, then the wording
  itself is not shown.

## Out of scope

Editing a meal plan by hand.
