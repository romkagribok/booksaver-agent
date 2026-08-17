---
id: 053-post-promotion-browser-migration
unit: 004-post-promotion-browser-migration
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: blocked
stories:
  - 001-migrate-inventory-perception-after-promotion
  - 002-retire-legacy-price-selectors-after-rollback
created: 2026-08-16T19:18:41Z
started: null
completed: null
current_stage: null
stages_completed: []
requires_bolts:
  - 052-agentic-browser-qualification
enables_bolts: []
requires_units:
  - 003-agentic-browser-qualification
blocks: true
complexity:
  avg_complexity: 3
  avg_uncertainty: 3
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 053-post-promotion-browser-migration

## Objective

After explicit price-path promotion, qualify inventory/account capabilities and retire legacy price
selectors only after the complete rollback window.

## Stories Included

- US-153 and US-154 (Should).

## Status

Blocked on bolt 052 live qualification and explicit promotion. No construction may start early.

## Success Criteria

- [ ] Inventory preserves completeness-gated reconciliation and repeats qualification.
- [ ] Legacy price selectors remain available for 30 rollback days, then require release approval.
- [ ] `/connect` Playwright and server verification remain unchanged.
