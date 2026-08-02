---
id: 001-recover-complete-booking-inventory-discovery
unit: 002-agent-assisted-booking-inventory
intent: 021-booking-browser-llm-recovery
status: complete
priority: must
created: 2026-08-02T18:07:49.000Z
assigned_bolt: 039-agent-assisted-booking-inventory
implemented: true
---

# Story: Recover Complete Booking Inventory Discovery

## User Story

**As a** BookSaver user
**I want** `/bookings` and prerequisite account refreshes to recover from Booking.com page drift
**So that** my authoritative reservations remain discoverable without manual data entry

## Acceptance Criteria

- [ ] **Given** deterministic inventory entry/readiness fails on an authenticated supported page,
  **When** allowance exists, **Then** the shared agent receives a narrow inventory recovery goal.
- [ ] **Given** scope, pagination, or detail navigation changes, **When** visible allowlisted read-only
  controls can recover them, **Then** traversal continues and every action is re-verified.
- [ ] **Given** deterministic parsing is unsupported or ambiguous, **When** bounded interpretation is
  available, **Then** typed positive candidates are validated before reconciliation.
- [ ] **Given** script success, **When** discovery completes, **Then** no LLM call occurs.
- [ ] **Given** `/bookings`, post-connect, `/checknow`, or scheduled synchronization, **When** inventory
  runs, **Then** all triggers use the same fallback-capable source once per caller batch.

## Technical Notes

- Inventory steps share the hardened BrowserAgent but use inventory-specific goals/verifiers.
- Add a user/operation-scoped inventory interpreter port and factory method.
- Preserve current page/reservation caps and allowlisted URL traversal.

## Dependencies

### Requires

- Unit 1 complete.
- Existing booking account synchronization core.

### Enables

- `002-preserve-completeness-and-safety-under-agent-assistance`
- `003-explain-and-observe-inventory-recovery`

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Auth wall or captcha | No recovery prompt containing login evidence; fail with specific guidance |
| Missing stable remote identity | Candidate rejected; no synthesized identity |
| More than safe page/reservation caps | Incomplete bounded result, no unbounded agent work |

## Out of Scope

- Private API reverse engineering or native Booking.com app automation.
