---
id: 094-jev-currency-pin
unit: 002-jev-currency-pin
intent: 028-reservation-change-reconciliation
type: ddd-construction-bolt
status: in-progress
stories:
  - 001-pin-page-currency
created: "2026-11-02T20:51:19Z"
started: "2026-11-03T00:52:47Z"
completed: null
current_stage: test
stages_completed:
  - name: domain-model
    completed: "2026-11-03T00:52:47Z"
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: "2026-11-03T00:52:47Z"
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: "2026-11-03T00:52:47Z"
    artifact: ddd-02-technical-design.md
  - name: implement
    completed: "2026-11-03T00:52:47Z"
    artifact: src/booksaver/infrastructure/browser/jev_price_executor.py
requires_bolts: []
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 094-jev-currency-pin

## Overview

Booked currency on the Jev property page after a redirect.

## Objective

Deliver FR-6 of intent 028-reservation-change-reconciliation.

## Stories Included

- [ ] US-229: Keep the Jev page in the booked currency (001-pin-page-currency; Must)

## Bolt Type

**Type**: DDD Construction Bolt

## Stages

- [ ] 1. Domain model
- [ ] 2. Technical design
- [ ] 3. ADR analysis
- [ ] 4. Implement
- [ ] 5. Test
