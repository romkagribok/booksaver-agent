---
id: 099-no-anthropic-key
unit: 002-no-anthropic-key
intent: 030-jev-only-booksaver
type: ddd-construction-bolt
status: complete
stories:
  - 001-route-everyone-to-jev
  - 002-drop-claude-discovery-fallback
  - 003-start-without-anthropic-key
created: "2026-11-04T16:13:23Z"
started: "2026-11-06T00:27:55Z"
completed: "2026-11-06T16:24:00Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: "2026-11-06T00:27:55Z"
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: "2026-11-06T00:27:55Z"
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: "2026-11-06T00:27:55Z"
    artifact: adr-062-no-consent-gate-inform-once.md
  - name: implement
    completed: "2026-11-06T00:40:00Z"
    artifact: src/booksaver/daemon/check_coordinator.py
  - name: test
    completed: "2026-11-06T00:40:00Z"
    artifact: ddd-03-test-report.md
requires_bolts:
  - 098-jev-reservation-reader
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 099-no-anthropic-key

## Overview

No Anthropic key needed.

## Objective

Deliver FR-7 to FR-10 of intent 030-jev-only-booksaver.

## Stories Included

- [ ] US-246: Route every user to Jev (001-route-everyone-to-jev; Must)
- [ ] US-247: Drop the Claude discovery fallback (002-drop-claude-discovery-fallback; Must)
- [ ] US-248: Start without the Anthropic key (003-start-without-anthropic-key; Must)

## Bolt Type

**Type**: DDD Construction Bolt
