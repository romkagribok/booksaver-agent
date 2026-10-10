---
id: 002-exclude-worse-meal-offers
unit: 002-meal-aware-offers
intent: 027-meal-plan-equivalence
status: draft
priority: must
created: "2026-10-10T01:49:45Z"
assigned_bolt: 091-meal-aware-offers
implemented: false
---

# US-223: Exclude offers with a worse meal plan

## User story

As a BookSaver user, I want offers with fewer meals than my reservation excluded, so that a
lower price is only reported when it is actually better.

## Assigned requirement

FR-1, FR-7.

## Acceptance criteria

- [ ] Given an offer whose meal plan ranks below the reservation's, when offers are selected, then
  it is excluded with its own reason.
- [ ] Given an offer with an `unknown` meal plan and a reservation that includes meals, when
  offers are selected, then it is excluded.
- [ ] Given an offer with the same or a better meal plan, when offers are selected, then it stays
  eligible.
- [ ] Given a reservation whose meal plan is `unknown`, when offers are selected, then none is
  excluded on meals.
- [ ] Given every otherwise-equivalent offer excluded on meals, when the check ends, then it
  reports that no equivalent offer was found and is not a failure.
- [ ] Given the amended boundary, when the bolt completes, then `AGENTS.md` states it.

## Out of scope

Other rate conditions.
