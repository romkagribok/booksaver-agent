---
id: 002-show-every-reservation-and-reason
unit: 002-synchronized-booking-interface
intent: 019-booking-account-synchronization
status: complete
priority: must
created: 2026-07-27T16:28:04.000Z
assigned_bolt: 036-synchronized-booking-interface
implemented: true
---

# Story: US-117 Show future upcoming reservations and eligibility reasons

## User Story

**As a** BookSaver user
**I want** `/bookings` to show my future upcoming reservations and their eligibility
**So that** the list stays relevant while still explaining which future stays are monitored.

## Acceptance Criteria

- [ ] Bounded pagination/selection exposes every synchronized reservation whose remote lifecycle is
  upcoming and whose check-in date is later than the current UTC date.
- [ ] Each summary shows property/dates, lifecycle, eligibility, all reasons, and observation time.
- [ ] Completed, past, current-stay, cancelled, absent, and missing-date reservations are omitted
  while remaining synchronized internally.
- [ ] Eligible reservations expose only applicable read-only savings/check actions.
- [ ] Ineligible reservations expose no price-check action.
- [ ] Auth-required results offer `/connect`; retryable failures offer a safe refresh.
- [ ] No manual booking or guided-rebook action appears.

## Dependencies

### Requires
- US-116.

### Enables
- None.

## Out of Scope

- Booking.com mutation or non-hotel inventory.
