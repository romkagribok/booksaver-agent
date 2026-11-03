---
id: 095-monitoring-stall-notice
unit: 003-monitoring-stall-notice
intent: 028-reservation-change-reconciliation
type: ddd-construction-bolt
status: planned
stories:
  - 001-notify-stalled-monitoring
  - 002-recover-without-repeats
created: "2026-11-02T20:51:19Z"
started: null
completed: null
current_stage: null
stages_completed: []
requires_bolts:
  - 093-reservation-change-sync
  - 094-jev-currency-pin
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 095-monitoring-stall-notice

## Overview

Stall evaluation, reason wording, durable notice state.

## Objective

Deliver FR-7, FR-8 of intent 028-reservation-change-reconciliation.

## Stories Included

- [ ] US-230: Tell the user monitoring has stalled (001-notify-stalled-monitoring; Must)
- [ ] US-231: Report recovery without repeats (002-recover-without-repeats; Must)

## Bolt Type

**Type**: DDD Construction Bolt

## Stages

- [ ] 1. Domain model
- [ ] 2. Technical design
- [ ] 3. ADR analysis
- [ ] 4. Implement
- [ ] 5. Test
