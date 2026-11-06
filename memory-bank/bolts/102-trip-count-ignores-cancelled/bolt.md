---
id: 102-trip-count-ignores-cancelled
unit: 001-trip-count-ignores-cancelled
intent: 031-cancelled-card-trip-count
type: simple-construction-bolt
status: in-progress
stories:
  - 001-verify-trip-with-cancelled-card
created: "2026-11-05T23:59:59Z"
started: "2026-11-05T23:59:59Z"
completed: null
current_stage: test
stages_completed:
  - name: plan
    completed: "2026-11-05T23:59:59Z"
    artifact: implementation-plan.md
  - name: implement
    completed: "2026-11-06T00:21:42Z"
    artifact: implementation-walkthrough.md
  - name: test
    completed: "2026-11-06T00:21:42Z"
    artifact: test-walkthrough.md
requires_bolts: []
enables_bolts: []
requires_units: []
blocks: false
---

# Bolt: 102-trip-count-ignores-cancelled

## Objective

Verify trips that contain a cancelled card.

## Stories Included

- [ ] US-254: Verify a trip that contains a cancelled card (001-verify-trip-with-cancelled-card; Must)
