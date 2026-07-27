---
id: 001-discover-complete-authenticated-inventory
unit: 001-booking-account-sync-core
intent: 019-booking-account-synchronization
status: complete
priority: must
created: 2026-07-27T16:28:04.000Z
assigned_bolt: 034-booking-account-sync-core
implemented: true
---

# Story: US-112 Discover the complete authenticated reservation inventory

## User Story

**As an** authorized BookSaver user
**I want** every hotel reservation in my authenticated Booking.com account discovered read-only
**So that** I see complete account state without entering reservation facts.

## Acceptance Criteria

- [ ] A caller-owned clean browser context traverses supported reservation inventory and pagination.
- [ ] The result explicitly reports complete, incomplete, or failed enumeration.
- [ ] Every observed hotel reservation carries remote identity, lifecycle, required facts, and
  redacted provenance, including ineligible reservations.
- [ ] The adapter exposes no cancellation, modification, booking, checkout, or payment operation.
- [ ] Unsupported/ambiguous layouts fail closed without asserting inventory absence.

## Dependencies

### Requires
- Existing encrypted session and browser coordinator.

### Enables
- US-113, US-114, US-115.

## Out of Scope

- Persistence reconciliation, Telegram rendering, or live candidate pricing.
