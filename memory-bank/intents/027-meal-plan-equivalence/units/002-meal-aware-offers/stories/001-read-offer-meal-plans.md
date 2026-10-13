---
id: 001-read-offer-meal-plans
unit: 002-meal-aware-offers
intent: 027-meal-plan-equivalence
status: complete
priority: must
created: "2026-10-10T01:49:45Z"
assigned_bolt: 091-meal-aware-offers
implemented: true
---

# US-222: Read each offer's meal plan

## User story

As a BookSaver user, I want each candidate offer's meal plan read from the rate it belongs
to, so that a room-only rate is not mistaken for my breakfast rate.

## Assigned requirement

FR-6, FR-11.

## Acceptance criteria

- [ ] Given a candidate rate, when a price method reports it, then it carries a meal plan and the
  verbatim text it relied on.
- [ ] Given a reported meal plan, when code cannot ground it in that text, then it is `unknown`.
- [ ] Given a rate that states nothing about meals, when it is read, then its meal plan is `none`.
- [ ] Given saved real property pages, when the reader runs on them, then every rate's meal plan
  matches the page before production enablement. **Descoped**: see the requirements amendment
  of 2026-10-13T13:51:32Z; replaced by a production read-back after release.

## Out of scope

Changing which price method is authoritative.
