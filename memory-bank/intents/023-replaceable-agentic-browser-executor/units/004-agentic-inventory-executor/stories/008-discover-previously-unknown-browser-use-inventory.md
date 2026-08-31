---
id: 008-discover-previously-unknown-browser-use-inventory
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-08-31T21:57:00Z
assigned_bolt: 062-agentic-inventory-executor
completed: 2026-08-31T23:33:00Z
implemented: true
---

# Story: Discover Previously Unknown Browser Use Inventory

## User Story

**As a** BookSaver user
**I want** `/bookings` to inspect the current Booking.com upcoming inventory even when a saved stay
is already visible
**So that** newly created reservations are discovered instead of the command merely refreshing
cached rows

## Acceptance Criteria

- [x] A semantic match to one saved reservation is positive evidence but never ends the inventory
  episode before the agent can inspect other visible upcoming reservations.
- [x] A previously unknown reservation can be submitted only with a visibly explicit Booking.com
  confirmation number and recognized scope.
- [x] Visible optional facts are submitted separately from stable identity so malformed optional
  evidence cannot discard a valid new positive.
- [x] Repeated submissions for one confirmation merge without conflicting facts, duplicate rows, or
  authority over absence, eligibility, authentication, or transactions.
- [x] The task directs Browser Use to enumerate visible upcoming cards and pagination within the
  existing action, deadline, and cost caps; it no longer defines one current positive as success.
- [x] A regression test proves a known visible stay does not invoke an early-return path.
- [x] A bounded authenticated VPS replay starts from an isolated clone with no saved reservations
  and rediscovers the real visible booking without mutating production data.

## Dependencies

- US-160, US-161, ADR-039, ADR-040, and ADR-041.

## Out of Scope

- Absence reconciliation; price execution; Browser Use Cloud; selectors; new provider secrets;
  changes to `/connect`; autonomous cancellation, reservation, purchase, or payment.
