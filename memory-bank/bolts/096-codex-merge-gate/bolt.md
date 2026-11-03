---
id: 096-codex-merge-gate
unit: 004-codex-merge-gate
intent: 028-reservation-change-reconciliation
type: simple-construction-bolt
status: in-progress
stories:
  - 001-require-codex-review
created: "2026-11-03T01:23:31Z"
started: "2026-11-03T01:23:31Z"
completed: null
current_stage: test
stages_completed:
  - name: plan
    completed: "2026-11-03T01:23:31Z"
    artifact: implementation-plan.md
  - name: implement
    completed: "2026-11-03T01:23:31Z"
    artifact: implementation-walkthrough.md
requires_bolts: []
enables_bolts: []
requires_units: []
blocks: false
---

# Bolt: 096-codex-merge-gate

## Objective

Replace the Bugbot merge gate with a Codex merge gate.

## Stories Included

- [ ] US-232: Require the Codex review before merge (001-require-codex-review; Must)
