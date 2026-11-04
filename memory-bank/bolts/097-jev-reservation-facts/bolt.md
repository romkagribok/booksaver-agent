---
id: 097-jev-reservation-facts
unit: 001-jev-reservation-facts
intent: 029-jev-reservation-facts
type: ddd-construction-bolt
status: in-progress
stories:
  - 001-prove-selected-total
  - 002-prove-selected-refund-terms
  - 003-bound-and-surface-assisted-syncs
created: "2026-11-03T19:24:37Z"
started: "2026-11-03T21:24:43Z"
completed: null
current_stage: test
stages_completed:
  - name: domain-model
    completed: "2026-11-03T21:24:43Z"
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: "2026-11-03T21:24:43Z"
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: "2026-11-03T21:24:43Z"
    artifact: adr-060-jev-selects-code-proves.md
  - name: implement
    completed: "2026-11-03T21:56:42Z"
    artifact: src/booksaver/infrastructure/browser/jev_reservation_facts.py
  - name: test
    completed: "2026-11-03T21:56:42Z"
    artifact: ddd-03-test-report.md
requires_bolts: []
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 097-jev-reservation-facts

## Overview

Jev selects, code proves: booked totals and refund terms the code reader left unknown.

## Objective

Deliver FR-1 to FR-8 of intent 029-jev-reservation-facts.

## Stories Included

- [ ] US-240: Prove a Jev-selected booked total (001-prove-selected-total; Must)
- [ ] US-241: Prove Jev-selected refund terms (002-prove-selected-refund-terms; Must)
- [ ] US-242: Keep assisted syncs bounded and visible (003-bound-and-surface-assisted-syncs; Must)

## Bolt Type

**Type**: DDD Construction Bolt
