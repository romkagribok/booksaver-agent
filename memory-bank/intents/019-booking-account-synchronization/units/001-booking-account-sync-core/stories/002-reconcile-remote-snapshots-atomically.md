---
id: 002-reconcile-remote-snapshots-atomically
unit: 001-booking-account-sync-core
intent: 019-booking-account-synchronization
status: complete
priority: must
created: 2026-07-27T16:28:04.000Z
assigned_bolt: 034-booking-account-sync-core
implemented: true
---

# Story: US-113 Reconcile remote reservation snapshots atomically

## User Story

**As an** authorized BookSaver user
**I want** repeated account synchronization to update stable reservation records safely
**So that** local monitoring reflects Booking.com without duplicates or false deletions.

## Acceptance Criteria

- [ ] Remote identity is unique within a user and idempotently maps to one stable local booking ID.
- [ ] Distinct remote identities remain separate even when their reservation facts are equivalent.
- [ ] Complete runs may mark unseen prior reservations absent; partial/failed runs cannot.
- [ ] Explicit lifecycle/fact changes update snapshots and invalidate current savings atomically.
- [ ] Cancelled, past, and absent records remain visible after cutover.
- [ ] Reconciliation never infers replacement relationships.

## Dependencies

### Requires
- US-112.

### Enables
- US-114, US-116, US-117.

## Out of Scope

- User-trigger orchestration or legacy data preservation.
