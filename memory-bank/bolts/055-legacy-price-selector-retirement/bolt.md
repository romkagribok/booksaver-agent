---
id: 055-legacy-price-selector-retirement
unit: 005-legacy-price-selector-retirement
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: blocked
stories:
  - 001-retire-legacy-price-selectors-after-rollback
created: 2026-08-25T13:00:00Z
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
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: Legacy Price Selector Retirement

## Objective

Remove the legacy price path only after explicit price promotion and a complete 30-day rollback
window without regression.

## Stories Included

- [ ] **US-154**: Retire legacy price selectors after rollback - Priority: Should

## Status

Blocked on Bolt 052 live price qualification, explicit promotion, and the rollback window.

## Success Criteria

- [ ] Removal has separate release approval and rollback evidence.
- [ ] `/connect` Playwright custody remains unchanged.
