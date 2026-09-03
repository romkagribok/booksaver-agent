---
id: 004-route-and-account-for-bounded-execution
unit: 001-agentic-executor-control-plane
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: '2026-08-16T19:18:41Z'
assigned_bolt: 050-agentic-executor-control-plane
implemented: true
---

# Story: Route and Account for Bounded Execution

## User Story

**As a** deployment owner
**I want** fail-closed routing and exact shared limits
**So that** canarying cannot expose invitees or exceed my safety and cost ceilings

## Acceptance Criteria

- [x] Routing is closed and config-validated; `legacy`, `owner_canary`, and `agentic` retain their
  original meanings, ADR-045 adds `consented_users`, and legacy remains the default.
- [x] Owner canary admits only the owner; agentic requires qualification and current disclosure
  consent for invited users.
- [x] Fifteen total actions, six computer-use actions, 180 seconds, USD 1/check, and USD 10/day are
  enforced across both semantic and visual paths.
- [x] Reservations reconcile actual usage and cannot be bypassed by errors or partial calls.

## Dependencies

- US-143, current coordinator admission, and model cost ledger.

## Out of Scope

- Live promotion approval.

## Amendment

US-170 and ADR-045 add explicit early rollout for currently disclosed invitees without changing the
qualification-gated `agentic` route or the limits established by this story.
