---
intent: 006-telegram-booking-management
created: 2026-07-18T22:40:07Z
status: complete
---

# Units: Telegram Booking Management

## Requirement-to-Unit Mapping

- **FR-1** → `001-conversational-booking-management`
- **FR-2** → `001-conversational-booking-management`
- **FR-3** → `001-conversational-booking-management`
- **FR-4** → `001-conversational-booking-management`

## Unit 001: Conversational Booking Management

- **Purpose**: Safely edit and permanently delete caller-owned monitored bookings through Telegram.
- **Unit Type**: CLI/inbound adapter.
- **Default Bolt Type**: `simple-construction-bolt`.
- **Dependencies**: Completed booking registration/persistence, user scoping, Telegram dialogs, and
  interactive command navigation.
- **Interface**: `/editbooking`, `/deletebooking`, `bedit:`/`bdel:` callbacks, dialog messages, and
  explicit booking-repository mutations.

## Independence

The capability is implemented and tested as one cohesive command unit. It uses existing domain
types and storage but adds no deployment component, schema, or Booking.com integration.
