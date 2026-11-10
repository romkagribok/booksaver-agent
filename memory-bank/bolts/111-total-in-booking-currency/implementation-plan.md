---
stage: plan
bolt: 111-total-in-booking-currency
created: 2026-11-10T13:26:27Z
---

# Implementation Plan

## Objective

The booked total is read in the booking's currency, so price checks of that booking run in it.

## Deliverables

- `booking_currency(area)`: the currency of the price area's amount-only lines, when they agree.
- `JevReservationFacts`: total options limited to lines in that currency; a total in another
  currency never counts; adapter `jev-reservation-facts-v5`.
- Unit tests; staged sync of user 4 and an Ayres price check.

## Dependencies

None. Reconciliation (ADR-061) and price checks are unchanged.

## Technical Approach

A bare amount is Booking.com's own price; a conversion carries words. This is a symbol-and-digit
test, independent of the page language. Unknown currency leaves today's behaviour.

## Acceptance Criteria

See US-263.

## Deviation

The first version asked Jev for the currency (`booking_currency` question). Staging at
2026-11-10T13:31Z showed Jev answering EUR for Ayres and Park Plaza; it was replaced before merge.
Human checkpoints skipped under the standing waiver (CLAUDE.local.md point 4).
