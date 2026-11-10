---
id: 111-total-in-booking-currency
unit: 001-total-in-booking-currency
intent: 038-booking-currency
type: simple-construction-bolt
status: complete
stories:
  - 001-total-in-booking-currency
created: "2026-11-10T13:26:27Z"
started: "2026-11-10T13:26:27Z"
completed: "2026-11-10T23:58:35Z"
current_stage: null
stages_completed:
  - name: plan
    completed: "2026-11-10T13:26:27Z"
    artifact: implementation-plan.md
  - name: implement
    completed: "2026-11-10T13:52:31Z"
    artifact: implementation-walkthrough.md
  - name: test
    completed: "2026-11-10T13:52:31Z"
    artifact: test-walkthrough.md
requires_bolts: []
enables_bolts: []
requires_units: []
blocks: false
---

# Bolt: 111-total-in-booking-currency

## Objective

The booked total is read in the booking's currency. Human stage checkpoints skipped under the
owner's standing waiver (CLAUDE.local.md point 4).

## Stories Included

- [x] US-263: The booked total is read in the booking's currency (001-total-in-booking-currency; Must)
