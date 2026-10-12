---
id: 001-record-reservation-meal-plan
unit: 001-reservation-meal-plan
intent: 027-meal-plan-equivalence
status: complete
priority: must
created: "2026-10-10T01:49:45Z"
assigned_bolt: 090-reservation-meal-plan
implemented: true
---

# US-220: Record the reservation's meal plan

## User story

As a BookSaver user, I want my reservation's meal plan recorded when my account is
synchronized, so that offers can later be compared like for like.

## Assigned requirement

FR-2, FR-3, FR-4.

## Acceptance criteria

- [ ] Given a `Meal Plan` row with explicit no-meal wording, when the page is parsed, then the
  meal plan is `none` and the wording is kept.
- [ ] Given a `Meal Plan` row with explicit inclusion wording, when the page is parsed, then the
  meal plan is the included value.
- [ ] Given a `Meal Plan` row with unrecognized wording or an unranked combination, when the page
  is parsed, then the meal plan is `unknown`.
- [ ] Given wording that prices a meal as an optional extra, when it is classified, then it is not
  an inclusion.
- [ ] Given no `Meal Plan` row and a recognized room name and guest row, when the page is parsed,
  then the meal plan is `none` with no wording; without the guest row or room it is `unknown`.
- [ ] Given a room facilities list that names a meal, when the page is parsed, then that list is
  not meal evidence.
- [ ] Given a provider-submitted reservation fact, when it is mapped, then it cannot set a meal
  plan.
- [ ] Given a parsed meal plan, when the reservation is saved, then the value and its wording (at
  most 200 characters) are stored and the value reaches the monitored booking.
- [ ] Given a saved reservation, when a later synchronization reads `unknown` or reads a page that
  states nothing, then a stated value is kept; a different stated value replaces it.
- [ ] Given a database at schema v20, when it is opened, then it migrates to v21 with every
  existing meal plan `unknown`.
- [ ] Given a production reservation that includes breakfast, when it is synchronized after
  release, then its meal plan reads `breakfast`.

## Out of scope

Offer selection and alerts.
