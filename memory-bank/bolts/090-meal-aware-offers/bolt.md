---
id: 090-meal-aware-offers
unit: 002-meal-aware-offers
intent: 027-meal-plan-equivalence
type: ddd-construction-bolt
status: planned
stories:
  - 001-read-offer-meal-plans
  - 002-exclude-worse-meal-offers
  - 003-state-meals-in-alerts
  - 004-apply-meal-rule-to-jev-arm
created: "2026-10-10T01:49:45Z"
started: null
completed: null
current_stage: null
stages_completed: []
requires_bolts: ['089-reservation-meal-plan']
enables_bolts: []
requires_units: []
blocks: true
---

# 090-meal-aware-offers

## Objective

Read each offer's meal plan, gate offer selection on it, and state both meal plans in alerts.

## Stories included

- [ ] US-218: Read each offer's meal plan (001-read-offer-meal-plans; Must)
- [ ] US-219: Exclude offers with a worse meal plan (002-exclude-worse-meal-offers; Must)
- [ ] US-220: State meal plans in savings alerts (003-state-meals-in-alerts; Must)
- [ ] US-221: Apply the meal rule to the Jev arm (004-apply-meal-rule-to-jev-arm; Must)

## Stages and expected outputs

- [ ] Domain model: ddd-01-domain-model.md.
- [ ] Technical design: ddd-02-technical-design.md.
- [ ] ADR analysis: record actual new or amended decisions and update the decision index.
- [ ] Implement: scoped source, tests, and migration where required.
- [ ] Test: ddd-03-test-report.md with actual commands and results.

## Scope notes

Starts after bolt 089 is released and its production readings are reviewed. Offer-side wording
is qualified against saved real property pages; nothing is assumed from memory.
