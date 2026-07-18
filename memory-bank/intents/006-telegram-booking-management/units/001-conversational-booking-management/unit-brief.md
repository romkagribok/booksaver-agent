---
unit: 001-conversational-booking-management
intent: 006-telegram-booking-management
phase: construction
status: complete
unit_type: cli
default_bolt_type: simple-construction-bolt
created: 2026-07-18T22:40:07.000Z
updated: 2026-07-18T23:19:09Z
---

# Unit Brief: Conversational Booking Management

## Purpose and Scope

Add discoverable Telegram edit/delete commands that operate only on caller-owned active bookings,
reuse existing domain validation, and preserve daemon/persistence integrity.

## Assigned Requirements

- **FR-1**: Discover booking management commands.
- **FR-2**: Edit a caller-owned booking interactively.
- **FR-3**: Delete a caller-owned booking with explicit confirmation.
- **FR-4**: Preserve monitoring and persistence integrity.

## Key Entities and Operations

- **Booking aggregate**: Existing identity, owner, immutable registration metadata, editable
  monitoring criteria, and active status.
- **Edit field group**: Enumerated property, dates, room, price, refund policy, occupancy, or
  confirmation selection followed by validated free-form values.
- **Delete confirmation**: Short-lived button decision that re-resolves ownership immediately before
  local cascade deletion.
- **Booking repository mutation**: Whole-aggregate update and transactional dependent-data deletion.

## Dependencies

- Intent 001 core booking domain and SQLite repository.
- Intent 003 Telegram gateway, dialogs, and user scoping.
- Intent 005 command catalog and callback router.
- Bolt 016 complete.

## Technical Constraints

- No schema or dependency change.
- Keep callback data within 64 bytes.
- Preserve booking ID, owner, registration timestamp, status, and linked history during edit.
- Delete dependent savings, rebook events/sessions, traces, and check history before the booking in
  one transaction.
- Invalidate savings opportunities on edit while retaining check and rebook audit history; the
  schema has no stale-opportunity state and old offers must not remain actionable.
- Refuse edit/delete while a non-terminal guided rebook session exists for the booking.
- Never treat global Telegram admission as booking ownership.

## Story Summary

- **Total Stories**: 4
- **Must Have**: 4
- **Should Have**: 0
- **Could Have**: 0

### Stories

- [ ] **US-048**: Discover edit and delete booking commands - Must - In Progress
- [ ] **US-049**: Edit an owned booking with selectable fields - Must - In Progress
- [ ] **US-050**: Delete an owned booking after confirmation - Must - In Progress
- [ ] **US-051**: Preserve mutation and scheduler integrity - Must - In Progress

## Success Criteria

- [ ] Native menu/help includes both commands.
- [ ] Booking and edit-field inputs are button-selectable and caller scoped.
- [ ] Domain-invalid edits never persist and unchanged fields remain exact.
- [ ] Deletion requires Confirm and atomically removes all linked local rows.
- [ ] Typed shortcuts, callbacks, dialogs, scheduler reads, and existing commands remain compatible.
- [ ] Ruff, mypy, focused tests, and full pytest pass.
