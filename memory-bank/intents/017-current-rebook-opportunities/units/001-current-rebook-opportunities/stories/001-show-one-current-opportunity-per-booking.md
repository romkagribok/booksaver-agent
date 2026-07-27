---
id: 001-show-one-current-opportunity-per-booking
unit: 001-current-rebook-opportunities
intent: 017-current-rebook-opportunities
status: complete
priority: must
created: 2026-07-27T02:10:44.000Z
assigned_bolt: 032-current-rebook-opportunities
implemented: true
---

# Story: Show One Current Opportunity per Booking

**Global story ID**: US-106

## User Story

**As a** Telegram user with savings on one or more reservations
**I want** one newest choice for each booking
**So that** repeated checks do not create duplicate or contradictory actions.

## Acceptance Criteria

- [x] Several opportunities for one active booking produce one newest button.
- [x] Two active bookings with opportunities produce two buttons.
- [x] Buttons are ordered by newest validation across bookings.
- [x] Equal timestamps resolve deterministically by persistence insertion order.
- [x] Archived and foreign-owned bookings produce no choices.

## Dependencies

Existing savings persistence, booking ownership, and Telegram picker.
