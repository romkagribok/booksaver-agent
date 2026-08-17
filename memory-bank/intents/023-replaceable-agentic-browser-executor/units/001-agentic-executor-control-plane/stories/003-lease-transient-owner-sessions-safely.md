---
id: 003-lease-transient-owner-sessions-safely
unit: 001-agentic-executor-control-plane
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: '2026-08-16T19:18:41Z'
assigned_bolt: 050-agentic-executor-control-plane
implemented: true
---

# Story: Lease Transient Owner Sessions Safely

## User Story

**As an** invited BookSaver user
**I want** my saved Booking session confined to one transient local check
**So that** a browser harness or model never receives my session material

## Acceptance Criteria

- [x] A lease is bound to owner, booking, job, deadline, and single consumption.
- [x] Cookies are injected only by local code into a fresh browser and absent from prompts/results.
- [x] Refreshed cookies require code-owned authentication verification before persistence eligibility.
- [x] Teardown destroys the profile on every terminal path.

## Dependencies

- Existing encrypted per-user session service and `/connect` verifier.

## Out of Scope

- Changing `/connect` capture or authentication authority.
