---
id: 001-retire-legacy-price-selectors-after-rollback
unit: 005-legacy-price-selector-retirement
intent: 023-replaceable-agentic-browser-executor
status: blocked
priority: should
created: 2026-08-16T19:18:41Z
updated: 2026-08-25T13:00:00Z
assigned_bolt: 055-legacy-price-selector-retirement
implemented: false
---

# Story: Retire Legacy Price Selectors After the Rollback Window

## User Story

**As a** BookSaver maintainer
**I want** obsolete price selectors removed after a successful rollback window
**So that** the project stops paying maintenance cost for two production paths

## Acceptance Criteria

- [ ] Legacy becomes rollback-only immediately after agentic price promotion and receives no selector
  maintenance.
- [ ] Removal requires 30 complete days without rollback and a separate release approval.
- [ ] Price-only Playwright selectors are removed without affecting `/connect` Playwright custody.
- [ ] Rollback documentation and config reject removed modes after the release boundary.

## Dependencies

- US-152 promotion and a clean 30-day rollback window.

## Out of Scope

- Retiring Playwright from `/connect`.
