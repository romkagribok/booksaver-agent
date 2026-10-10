---
id: 003-state-meals-in-alerts
unit: 002-meal-aware-offers
intent: 027-meal-plan-equivalence
status: draft
priority: must
created: "2026-10-10T01:49:45Z"
assigned_bolt: 090-meal-aware-offers
implemented: false
---

# US-220: State meal plans in savings alerts

As a BookSaver user, I want every savings alert to state my reservation's and the offer's
meal plan, so that I can see the comparison for myself.

## Acceptance criteria

- Every savings alert states both meal plans in plain words.
- When the reservation's meal plan is `unknown`, the alert says it could not be confirmed.
- A saved opportunity found before the reservation's meal plan was known is re-evaluated.
