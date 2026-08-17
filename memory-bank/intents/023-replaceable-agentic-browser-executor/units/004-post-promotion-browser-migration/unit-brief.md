---
unit: 004-post-promotion-browser-migration
intent: 023-replaceable-agentic-browser-executor
phase: inception
status: stories-defined
created: 2026-08-16T19:18:41Z
updated: 2026-08-16T19:18:41Z
unit_type: backend
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: Post-Promotion Browser Migration

## Purpose

After the price path proves safe and reliable, move remaining DOM-dependent account perception to
separate executor capabilities and retire the legacy price selectors after the rollback window.

## Scope

### In Scope

- Inventory observation capability with completeness evidence.
- Remaining DOM-dependent account checks.
- Thirty-day rollback-only price path and later selector removal.

### Out of Scope

- `/connect` server authentication verification or human login.
- Work before the owner canary and promotion checkpoint pass.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-10 | Post-promotion capability migration | Should |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 2 |
| Must Have | 0 |
| Should Have | 2 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-153 | Migrate inventory perception after promotion | Should | Blocked |
| US-154 | Retire legacy price selectors after rollback window | Should | Blocked |

## Dependencies

- Unit 003 live canary and explicit promotion approval.
- Existing completeness-gated account synchronization and `/connect` server contract.

## Constraints

- Do not start until price promotion is approved.
- Never weaken inventory completeness or `/connect` authentication authority.
- Removal requires no rollback during the complete 30-day window.

## Success Criteria

- [ ] Inventory adapter repeats price-path qualification and preserves completeness gating.
- [ ] Legacy price selectors are removed only after the rollback window and a separate release gate.
- [ ] Playwright remains for `/connect` until separately retired.

## Bolt Suggestions

- `053-post-promotion-browser-migration`: US-153 and US-154; blocked.
