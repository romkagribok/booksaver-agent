---
unit: 005-legacy-price-selector-retirement
intent: 023-replaceable-agentic-browser-executor
phase: inception
status: stories-defined
created: 2026-08-25T13:00:00Z
updated: 2026-08-25T13:00:00Z
unit_type: backend
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: Legacy Price Selector Retirement

## Purpose

Remove the legacy price path only after price promotion and its complete rollback window.

## Scope

### In Scope

- Thirty-day rollback-only price path and later selector removal.

### Out of Scope

- Agentic inventory, `/connect`, or work before the price promotion and rollback gates pass.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-11 | Deferred legacy price-selector retirement | Should |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 1 |
| Must Have | 0 |
| Should Have | 1 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-154 | Retire legacy price selectors after rollback | Should | Blocked |

## Dependencies

- Unit 003 explicit price promotion and a clean 30-day rollback window.

## Success Criteria

- [ ] Price-only selectors are removed only after a separate release approval.
- [ ] `/connect` Playwright custody remains unchanged.

## Bolt Suggestions

- `055-legacy-price-selector-retirement`: US-154; blocked.
