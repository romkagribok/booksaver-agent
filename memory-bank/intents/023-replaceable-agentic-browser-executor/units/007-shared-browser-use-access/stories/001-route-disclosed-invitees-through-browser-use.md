---
id: 001-route-disclosed-invitees-through-browser-use
unit: 007-shared-browser-use-access
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-09-03T23:30:00.000Z
assigned_bolt: 065-shared-browser-use-access
implemented: true
---

# Story: Route Disclosed Invitees Through Browser Use

## User Story

**As a** deployment owner
**I want** every active invited user who accepts the current disclosure to use Browser Use for
inventory and price checks
**So that** invited users receive the same DOM-resilient manual and scheduled execution path as I do

## Acceptance Criteria

- [x] A closed `consented_users` route admits the owner without qualification and admits an active
  invitee only when the stored disclosure version matches the current configuration.
- [x] Missing or stale invitee consent, explicit legacy routing, and recorded regression do not
  start Browser Use price execution.
- [x] Existing owner-canary and qualification-gated agentic routes retain their prior meaning.
- [x] `/checknow` and scheduled price checks resolve the same route and executor.
- [x] Agentic inventory continues to use Browser Use for the owner and every currently disclosed
  active invitee; no same-job fallback or new browser authority is introduced.
- [x] Qualification state is observed but never fabricated or promoted by selecting the new route.

## Dependencies

- US-152, US-160 through US-169, ADR-038, ADR-043, and ADR-044.
