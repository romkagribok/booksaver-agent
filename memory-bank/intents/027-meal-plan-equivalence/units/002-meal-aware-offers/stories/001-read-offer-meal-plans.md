---
id: 001-read-offer-meal-plans
unit: 002-meal-aware-offers
intent: 027-meal-plan-equivalence
status: draft
priority: must
created: "2026-10-10T01:49:45Z"
assigned_bolt: 090-meal-aware-offers
implemented: false
---

# US-218: Read each offer's meal plan

As a BookSaver user, I want each candidate offer's meal plan read from the rate it belongs
to, so that a room-only rate is not mistaken for my breakfast rate.

## Acceptance criteria

- Every price path that can produce a savings alert reports a meal plan per candidate rate with
  the verbatim text it relied on.
- Code grounds the reported value against that text; an ungrounded value is `unknown`.
- A rate that states nothing about meals is `none`.
- Wording is qualified against saved real property pages before production enablement.
