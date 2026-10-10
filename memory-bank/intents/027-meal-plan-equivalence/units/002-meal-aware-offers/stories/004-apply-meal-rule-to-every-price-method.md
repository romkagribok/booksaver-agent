---
id: 004-apply-meal-rule-to-every-price-method
unit: 002-meal-aware-offers
intent: 027-meal-plan-equivalence
status: draft
priority: must
created: "2026-10-10T01:49:45Z"
assigned_bolt: 091-meal-aware-offers
implemented: false
---

# US-225: Apply the meal rule to every price method

## User story

As the owner, I want the meal rule applied by whichever price method is authoritative and by
a paired comparison arm, so that results stay like for like.

## Assigned requirement

FR-10.

## Acceptance criteria

- [ ] Given Jev as the price method, when it reports an offer, then the offer carries a grounded
  meal plan or `unknown`.
- [ ] Given the LLM price path as the price method, when it reports an offer, then the same holds.
- [ ] Given any price method, when offers are selected, then they pass through the same rule.

## Out of scope

Retiring a price method.
