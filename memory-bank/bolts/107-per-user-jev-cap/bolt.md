---
id: 107-per-user-jev-cap
unit: 001-per-user-jev-cap
intent: 036-per-user-limits
type: simple-construction-bolt
status: complete
stories:
  - 001-per-user-jev-cap
created: "2026-11-10T00:46:00Z"
started: "2026-11-10T00:46:00Z"
completed: "2026-11-10T00:48:47Z"
current_stage: null
stages_completed:
  - name: plan
    completed: "2026-11-10T00:46:00Z"
    artifact: implementation-plan.md
  - name: implement
    completed: "2026-11-10T00:48:47Z"
    artifact: implementation-walkthrough.md
  - name: test
    completed: "2026-11-10T00:48:47Z"
    artifact: test-walkthrough.md
requires_bolts: []
enables_bolts: []
requires_units: []
blocks: false
---

# Bolt: 107-per-user-jev-cap

## Objective

Jev daily cap per user; check limit default 150.

## Stage checkpoints

Owner waived the per-stage human checkpoints for this bolt on 2026-11-10 ("Record all, no stage
stops"); the finished PR is reviewed before commit, merge and deploy.

## Stories Included

- [ ] US-259: Each user has their own Jev daily cap and a check limit that fits their bookings (001-per-user-jev-cap; Must)
