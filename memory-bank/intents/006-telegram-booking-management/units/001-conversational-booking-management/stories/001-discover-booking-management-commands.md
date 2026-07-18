---
id: 001-discover-booking-management-commands
unit: 001-conversational-booking-management
intent: 006-telegram-booking-management
status: complete
priority: must
created: 2026-07-18T22:40:07.000Z
assigned_bolt: 017-conversational-booking-management
implemented: true
---

# Story: Discover Booking Management Commands

**Global story ID**: US-048

## User Story

**As an** authorized Telegram user
**I want** edit and delete commands to appear in Telegram and `/help`
**So that** I can discover booking-management capabilities without documentation

## Acceptance Criteria

- [ ] `/editbooking` and `/deletebooking` share the authoritative command catalog.
- [ ] Both commands publish in applicable native command scopes and render in help/welcome text.
- [ ] Existing command names and owner-only scoping remain unchanged.

## Dependencies

- US-043 command catalog and native publication.
