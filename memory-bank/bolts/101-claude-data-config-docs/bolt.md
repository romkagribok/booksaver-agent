---
id: 101-claude-data-config-docs
unit: 004-claude-data-config-docs
intent: 030-jev-only-booksaver
type: ddd-construction-bolt
status: in-progress
stories:
  - 001-drop-claude-tables
  - 002-retire-claude-config
  - 003-update-docs-and-issues
created: "2026-11-04T16:13:23Z"
started: "2026-11-06T03:03:29Z"
completed: null
current_stage: test
stages_completed:
  - name: domain-model
    completed: "2026-11-06T03:03:29Z"
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: "2026-11-06T03:03:29Z"
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: "2026-11-06T03:03:29Z"
    artifact: adr-063-typesafe-jev-is-the-only-model-provider.md
  - name: implement
    completed: "2026-11-06T03:03:29Z"
    artifact: src/booksaver/application/load_config.py
  - name: test
    completed: "2026-11-06T03:03:29Z"
    artifact: ddd-03-test-report.md
requires_bolts:
  - 100-delete-claude-code
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 101-claude-data-config-docs

## Overview

Claude data, config and docs.

## Objective

Deliver FR-13 to FR-15 of intent 030-jev-only-booksaver.

## Stories Included

- [ ] US-251: Drop the Claude tables (001-drop-claude-tables; Must)
- [ ] US-252: Retire the Claude config keys (002-retire-claude-config; Must)
- [ ] US-253: Update docs and close the issues (003-update-docs-and-issues; Must)

## Bolt Type

**Type**: DDD Construction Bolt
