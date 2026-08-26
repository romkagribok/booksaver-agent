---
id: 001-execute-positive-only-agentic-inventory
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-08-25T13:00:00.000Z
assigned_bolt: 053-agentic-inventory-executor
implemented: true
---

# Story: Execute Positive-Only Agentic Inventory

## User Story

**As an** authorized BookSaver user
**I want** inventory discovery to use semantic and visual browser perception
**So that** ordinary Booking.com DOM changes do not block current reservation checks

## Acceptance Criteria

- [x] A separate provider-neutral inventory port returns typed positive observations and traversal
  evidence without provider SDK types or session material.
- [x] Every disclosed authorized user routes inventory through local Stagehand and one guarded
  computer-use fallback; legacy inventory remains a capability-specific rollback.
- [x] BookSaver validates identities and facts, derives eligibility, and persists only accepted
  current-run positive observations.
- [x] Agentic evidence never marks unseen rows absent; failed or partial runs preserve last-safe
  inventory.
- [x] Only a booking positively re-observed in the current run may proceed to a price check.
- [x] Bare `/checknow` shows saved choices, then the selected operation performs exactly one
  inventory verification before price execution under a shared budget and deadline.
- [x] `/bookings`, post-connect, `/checknow`, and scheduled flows preserve authorization, session,
  privacy, safety, cost, timeout, and teardown boundaries.
- [x] DOM-resilience, terminal-state, unsafe-action, egress, Docker runtime, and cross-trigger tests
  pass without BookSaver inventory selectors.

## Dependencies

- Units 001 and 002; ADR-027, ADR-028, ADR-036, and ADR-037.

## Out of Scope

- `/connect` authentication changes and legacy price-selector retirement.
