---
id: 004-cut-over-legacy-and-recover-failures
unit: 001-booking-account-sync-core
intent: 019-booking-account-synchronization
status: complete
priority: must
created: 2026-07-27T16:28:04.000Z
assigned_bolt: 035-booking-account-sync-core
implemented: true
---

# Story: US-115 Cut over legacy state and recover from synchronization failures

## User Story

**As the** BookSaver operator
**I want** obsolete manual booking state removed and synchronization failures safely visible
**So that** deployment starts from one authoritative source without hidden stale behavior.

## Acceptance Criteria

- [ ] The cutover migration atomically removes all legacy bookings and dependent booking history.
- [ ] Users, invites, encrypted sessions, keys, usage, and access state remain intact.
- [ ] The migration is idempotent, leaves no orphan rows, and requires a documented pre-upgrade backup.
- [ ] Failed/incomplete synchronization preserves prior post-cutover snapshots and cannot apply
  absence-based transitions.
- [ ] Auth, rate-limit, bot-wall, timeout, layout, pagination, extraction, and persistence failures
  remain redacted and distinguishable.
- [ ] No legacy mutation/import/matching path remains.

## Dependencies

### Requires
- US-112 through US-114.

### Enables
- Unit 002 and Bolt 036.

## Out of Scope

- Preserving pre-cutover booking or rebook history.
