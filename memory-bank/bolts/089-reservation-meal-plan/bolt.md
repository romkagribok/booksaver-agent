---
id: 089-reservation-meal-plan
unit: 001-reservation-meal-plan
intent: 027-meal-plan-equivalence
type: ddd-construction-bolt
status: planned
stories:
  - 001-record-reservation-meal-plan
  - 002-show-meal-plan-in-bookings
created: "2026-10-10T01:49:45Z"
started: null
completed: null
current_stage: null
stages_completed: []
requires_bolts: []
enables_bolts: ['090-meal-aware-offers']
requires_units: []
blocks: false
---

# 089-reservation-meal-plan

## Objective

Record each reservation's meal plan during account synchronization and show it in `/bookings`.

## Stories included

- [ ] US-216: Record the reservation's meal plan (001-record-reservation-meal-plan; Must)
- [ ] US-217: Show the meal plan in /bookings (002-show-meal-plan-in-bookings; Must)

## Stages and expected outputs

- [ ] Domain model: ddd-01-domain-model.md.
- [ ] Technical design: ddd-02-technical-design.md.
- [ ] ADR analysis: record actual new or amended decisions and update the decision index.
- [ ] Implement: scoped source, tests, and migration where required.
- [ ] Test: ddd-03-test-report.md with actual commands and results.

## Scope notes

No change to offer selection, alerts, or any price path. Released on its own so production
reservations confirm the readings before the gate is built on them.
