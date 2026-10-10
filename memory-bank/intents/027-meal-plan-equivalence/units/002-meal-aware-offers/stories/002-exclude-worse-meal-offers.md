---
id: 002-exclude-worse-meal-offers
unit: 002-meal-aware-offers
intent: 027-meal-plan-equivalence
status: draft
priority: must
created: "2026-10-10T01:49:45Z"
assigned_bolt: 090-meal-aware-offers
implemented: false
---

# US-219: Exclude offers with a worse meal plan

As a BookSaver user, I want offers with fewer meals than my reservation excluded, so that a
lower price is only reported when it is actually better.

## Acceptance criteria

- An offer whose meal plan ranks below the reservation's is excluded with its own reason.
- An offer with an `unknown` meal plan is excluded when the reservation includes meals.
- An offer with the same or a better meal plan stays eligible.
- When the reservation's meal plan is `unknown`, offers are not excluded on meals.
- A check whose otherwise-equivalent offers were all excluded on meals reports that no
  equivalent offer was found.
- ADR recorded and the `AGENTS.md` equivalence boundary amended.
