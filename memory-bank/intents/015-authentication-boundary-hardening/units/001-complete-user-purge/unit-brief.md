---
unit: 001-complete-user-purge
intent: 015-authentication-boundary-hardening
phase: inception
status: complete
unit_type: cli
default_bolt_type: simple-construction-bolt
created: 2026-07-26T19:41:07.000Z
updated: 2026-07-26T19:41:07.000Z
---

# Unit Brief: Complete User Purge

## Purpose

Make the owner-facing destructive purge match its promise by removing encrypted Booking.com
authentication state and preventing active login or operator import from restoring that state.

## Scope

### In Scope

- Target-scoped remote-auth cancellation under the manager lock.
- Target encrypted-session revocation/deletion before database purge.
- Typed and inline Telegram admin confirmation paths.
- Safe storage/SQLite failure reconciliation and regression coverage.

### Out of Scope

- Ordinary revoke behavior, owner deletion, bulk purge, or database schema changes.
- Waiting synchronously for the cancelled Chromium process to exit.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Purge all user-scoped authentication data | Must |

## Domain Concepts

- **Purge target**: resolved non-owner user whose local and Telegram identities remain available
  until cleanup finishes.
- **Capture boundary**: the remote-auth manager lock serializing success capture and cancellation.
- **Encrypted session**: target-owned file under `booking_sessions/`.
- **Revocation marker**: non-secret tombstone checked under the owner lock by every future save.

## Story Summary

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-097 | Remove encrypted authentication state during purge | Must | Complete |
| US-098 | Prevent in-flight authentication from surviving purge | Must | Complete |

## Dependencies

- Completed Bolt 009 user administration.
- Completed Bolt 024 encrypted per-user sessions.
- Completed Bolt 026 remote-authentication gateway.

## Constraints

- Session revocation failure aborts database deletion and cannot emit a success claim.
- SQLite failure after revocation exposes a retryable partial state rather than false success.
- Another user's session must never be touched.
- Missing session/attempt is a successful no-op.

## Success Criteria

- [x] Both admin confirmation paths remove the target session and database state.
- [x] Capture and import race tests prove no session can reappear after purge.
- [x] Failure tests prove storage and SQLite partial failures remain safe and visible.
- [x] Targeted and full quality gates pass.

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| 028-complete-user-purge | Simple | US-097, US-098 | Coordinate complete, race-safe user purge |
