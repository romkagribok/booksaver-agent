---
id: 003-delete-owned-booking-after-confirmation
unit: 001-conversational-booking-management
intent: 006-telegram-booking-management
status: complete
priority: must
created: 2026-07-18T22:40:07.000Z
assigned_bolt: 017-conversational-booking-management
implemented: true
---

# Story: Delete an Owned Booking After Confirmation

**Global story ID**: US-050

## User Story

**As an** authorized Telegram user
**I want** to select and explicitly confirm deletion of my booking
**So that** I can stop monitoring it without accidentally removing data

## Acceptance Criteria

- [ ] `/deletebooking` shows only caller-owned active bookings; typed unique prefixes are supported.
- [ ] The destructive scope is explained before separate Confirm and Cancel buttons.
- [ ] Confirm re-resolves current ownership and deletes; Cancel and stale/foreign/replayed callbacks
  leave protected data unchanged.
- [ ] Every callback is acknowledged and remains within Telegram's payload limit.

## Dependencies

- US-044 callback authorization and US-049 scoped booking selection patterns.
