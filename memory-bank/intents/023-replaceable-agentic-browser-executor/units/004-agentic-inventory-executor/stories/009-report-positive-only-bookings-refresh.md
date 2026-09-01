---
id: 009-report-positive-only-bookings-refresh
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-09-01T01:10:18.000Z
assigned_bolt: 063-agentic-inventory-executor
implemented: true
---

# Story: Report Accepted Positive Inventory Refreshes Accurately

## User Story

**As a** BookSaver user
**I want** `/bookings` to report when its agent accepted current reservations
**So that** a safe positive-only refresh is not presented as a browser failure

## Acceptance Criteria

- [x] A report with incomplete scope, no failure code, and at least one accepted current
  observation exposes a distinct positive-observation outcome.
- [x] Authoritative synchronization success continues to require complete inventory scope; the new
  outcome never permits deletion or absence inference for unseen saved reservations.
- [x] Telegram describes the positive-only result as refreshed current observations and explicitly
  says unseen saved reservations were preserved; it does not call the refresh failed or incomplete.
- [x] Incomplete runs with rejected or ambiguous evidence retain the existing incomplete warning.
- [x] A coordinator-level production-image replay waits for termination and exits zero only after
  receiving the distinct positive-observation outcome.

## Dependencies

- US-153, US-160, US-162, and ADR-039.

## Out of Scope

- Absence reconciliation; model-declared completeness; deletion of unseen reservations; browser
  action or destination changes; price execution; `/connect`; provider or secret changes.
