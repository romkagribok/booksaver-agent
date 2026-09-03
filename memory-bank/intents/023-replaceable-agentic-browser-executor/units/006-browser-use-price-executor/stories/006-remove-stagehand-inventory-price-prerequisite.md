---
id: 006-remove-stagehand-inventory-price-prerequisite
unit: 006-browser-use-price-executor
intent: 023-replaceable-agentic-browser-executor
status: draft
priority: must
created: 2026-09-03T00:36:00Z
assigned_bolt: 064-browser-use-price-executor
implemented: false
---

# Story: Remove the Stagehand Inventory Prerequisite from Price Operations

## User Story

**As a** BookSaver deployment owner
**I want** current-run inventory verification and price perception to use the proven Browser Use
executor
**So that** the default price flow cannot be blocked before Browser Use by the less reliable
Stagehand inventory adapter

## Acceptance Criteria

- [ ] `/checknow`, scheduled, post-connect, and `/bookings` agentic inventory triggers construct the
  same Browser Use inventory adapter in production composition.
- [ ] Each selected price operation still performs exactly one current-run inventory verification
  and preserves positive-only admission.
- [ ] Existing authorization, disclosure, session, validation, reconciliation, budget, deadline,
  safety, and privacy boundaries remain unchanged.
- [ ] `inventory_routing = "legacy"` remains explicit rollback; no same-job fallback is introduced.

## Dependencies

- US-160 through US-164.
