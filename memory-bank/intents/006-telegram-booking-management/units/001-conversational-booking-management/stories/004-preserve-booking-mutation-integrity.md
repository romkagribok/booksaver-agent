---
id: 004-preserve-booking-mutation-integrity
unit: 001-conversational-booking-management
intent: 006-telegram-booking-management
status: complete
priority: must
created: 2026-07-18T22:40:07.000Z
assigned_bolt: 017-conversational-booking-management
implemented: true
---

# Story: Preserve Booking Mutation Integrity

**Global story ID**: US-051

## User Story

**As the** BookSaver operator
**I want** booking edits and deletion to preserve repository invariants
**So that** monitoring and history do not become inconsistent

## Acceptance Criteria

- [ ] Whole-aggregate update retains identity, ownership, registration metadata, status, check
  history, and rebook audit history while invalidating savings evaluated from the old aggregate.
- [ ] Scheduler active-booking reads immediately observe edits and omit deleted rows.
- [ ] Deletion removes every booking-scoped dependent table row in one transaction.
- [ ] Missing targets and duplicate confirmation IDs fail predictably without partial writes.
- [ ] A non-terminal guided rebook session blocks edit/delete until its guarded workflow ends.

## Dependencies

- Existing schema v8 booking relationships and domain value objects.
