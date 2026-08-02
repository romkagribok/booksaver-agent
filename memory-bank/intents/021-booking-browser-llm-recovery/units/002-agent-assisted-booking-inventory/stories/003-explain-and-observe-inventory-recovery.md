---
id: 003-explain-and-observe-inventory-recovery
unit: 002-agent-assisted-booking-inventory
intent: 021-booking-browser-llm-recovery
status: complete
priority: must
created: 2026-08-02T18:07:49.000Z
assigned_bolt: 039-agent-assisted-booking-inventory
implemented: true
---

# Story: Explain and Observe Inventory Recovery

## User Story

**As a** BookSaver user or self-hosted operator
**I want** assisted inventory outcomes to be visible and accurately classified
**So that** I know whether reservations are fresh, preserved, or need reconnection without exposing private data

## Acceptance Criteria

- [ ] **Given** an assisted complete or partial synchronization, **When** `/bookings` renders, **Then**
  it identifies freshness and preserved evidence without model internals.
- [ ] **Given** authentication, LLM unavailable/error, no-progress, budget, unsupported layout, or
  incomplete traversal, **When** the run ends, **Then** a distinct redacted diagnostic and appropriate
  `/connect` or retry guidance is produced.
- [ ] **Given** an unexpected inventory worker exception, **When** completion renders, **Then** it never
  says “No future reservations found” solely because no report was returned.
- [ ] **Given** inventory LLM calls, **When** usage is inspected, **Then** every actual call consumed the
  requesting user's daily allowance and records provider/model/role metadata.
- [ ] **Given** an assisted run trace, **When** an operator inspects it, **Then** it contains step,
  outcomes, progress flags, calls/actions, timing, and result but no page text, confirmation identity,
  keys, cookies, or hidden reasoning.
- [ ] **Given** a caller is revoked during async work, **When** completion runs, **Then** no private
  callback result or cross-user data is sent.

## Technical Notes

- Extend synchronization audit/report metadata rather than overloading price-check traces.
- Preserve existing caller-scoped Telegram rendering and stale-inventory semantics.
- Add command-level tests for accepted, busy, stopping, assisted, incomplete, failed, and auth cases.

## Dependencies

### Requires

- Stories 001 and 002 in this unit.

### Enables

- Reviewable production operations and future provider comparisons.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| LLM budget exhausted but old inventory exists | Show preserved stale inventory plus fallback-unavailable warning |
| No prior inventory and refresh fails | Show refresh unavailable, not an empty-account conclusion |
| Callback user no longer active | Suppress completion disclosure |

## Out of Scope

- Cross-user aggregate reservation details in `/admin` or `/status`.
