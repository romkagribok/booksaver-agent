---
unit: 001-reservation-change-sync
bolt: 093-reservation-change-sync
stage: model
status: complete
created: 2026-11-03T00:49:01Z
updated: 2026-11-03T00:49:01Z
---

# Static Model - Reservation Change Sync

## Bounded Context

Account inventory reconciliation for one caller. Price checks and alerts consume the result.

## Domain Entities

- **Reservation**: identified by confirmation number and hotel. Stay, room, occupancy, refund facts
  and booked total describe its current state on Booking.com and may change.
- **Monitoring booking**: projection of an eligible reservation; keeps its identity across a change.
- **Saved opportunity**: valid only against the snapshot it was evaluated on.

## Value Objects

- **Fact provenance**: code-read (from the confirmation parser) or provider-submitted.
- **Converted breakdown**: rows in the session's display currency summing to an `approx.` amount,
  evidence that the booked-currency total below it includes tax. It is never stored.

## Domain Rules

1. Code-read facts with the same confirmation and hotel replace saved facts; provider-submitted
   facts that differ fail closed.
2. A change of dates, room or occupancy invalidates dependent facts that were not re-read.
3. A reservation without a verified total is ineligible and cannot alert, and returns by itself.
4. Any projection change removes saved opportunities in the same transaction.

## Ubiquitous Language

**Hold**: a reservation that is ineligible only because its changed stay has no verified total.
