---
id: 002-edit-owned-booking-selectively
unit: 001-conversational-booking-management
intent: 006-telegram-booking-management
status: complete
priority: must
created: 2026-07-18T22:40:07.000Z
assigned_bolt: 017-conversational-booking-management
implemented: true
---

# Story: Edit an Owned Booking Selectively

**Global story ID**: US-049

## User Story

**As an** authorized Telegram user
**I want** to select my booking and the fields to correct
**So that** future checks use accurate reservation details without UUID entry

## Acceptance Criteria

- [ ] `/editbooking` shows only caller-owned active bookings; typed unique prefixes are supported.
- [ ] Property, dates, room, price, refund policy, occupancy, and confirmation are buttons.
- [ ] Free-form values are validated with existing domain value objects.
- [ ] Completion re-resolves ownership, preserves untouched fields and identity, and rejects stale,
  foreign, invalid, or conflicting edits without protected action or disclosure.

## Dependencies

- US-029 user-scoped persistence and US-044 callback authorization.
