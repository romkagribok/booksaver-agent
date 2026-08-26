---
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
phase: inception
status: complete
created: 2026-08-25T13:00:00.000Z
updated: 2026-08-26T03:37:34.000Z
unit_type: backend
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: Agentic Inventory Executor

## Purpose

Replace selector-dependent Booking.com inventory perception with a provider-neutral Stagehand
capability for every disclosed authorized user, while BookSaver retains session custody,
validation, positive-only reconciliation, scheduling, and check authority.

## Scope

### In Scope

- `InventoryBrowserExecutor` request/result contracts and fake executor.
- Account-bound transient session leases and inventory-specific action/destination guards.
- Stagehand semantic scope, pagination, detail navigation, and typed extraction.
- One guarded Anthropic computer-use fallback without typing.
- Positive-only reconciliation and current-run check eligibility.
- `/bookings`, post-connect, `/checknow`, and scheduled routing.
- One inventory execution for a selected `/checknow` operation.
- Capability-specific config, rollback, redacted metrics, and tests.

### Out of Scope

- Model-authorized absence reconciliation or deletion of unseen rows.
- `/connect` authentication changes.
- Price routing, price promotion, or legacy price-selector removal.
- Selector learning, cached actions, managed browsers, or new provider secrets.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-10 | Provider-neutral agentic inventory execution | Must |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 1 |
| Must Have | 1 |
| Should Have | 0 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-153 | Execute positive-only agentic inventory | Must | Complete |

## Dependencies

- Units 001 and 002.
- Existing account synchronization, ADR-027 projection, and ADR-028 reconciliation rules.
- Existing disclosure, session vault, cost ledger, coordinator gate, and transient Chromium runtime.

## Constraints

- Every authorized disclosed user uses agentic inventory; price routing remains independent.
- Only current-run positive observations may unblock a check.
- Unseen rows are always preserved by this capability.
- Inventory and price in one operation share cost admission and deadline.
- Inventory computer use cannot type.

## Success Criteria

- [x] DOM-resilience fixtures pass without BookSaver inventory selectors.
- [x] All inventory triggers use the executor with one `/checknow` inventory run.
- [x] Current-run positives can proceed while cached-only rows cannot.
- [x] No agentic terminal can mark an unseen reservation absent.
- [x] Session, action, destination, privacy, cost, timeout, and teardown tests pass.

## Bolt Suggestions

- `053-agentic-inventory-executor`: US-153.
