---
intent: 031-cancelled-card-trip-count
phase: construction
status: construction
created: "2026-11-05T23:59:59Z"
updated: "2026-11-05T23:59:59Z"
---

# Requirements: A cancelled card does not make a trip unverifiable

## Intent overview

After the owner's dad cancelled one booking and rebooked another, every sync of his account was
`incomplete` (`trip_card_count`). His trip shows five hotel cards (one marked Canceled) and one car
rental, while Booking.com's trip count leaves out cancelled bookings (five). The reader counted the
cancelled card, never verified the trip, and so never retired his superseded Best Western
reservation, which would have produced a misleading stall message around 2026-11-06T05:35Z.
Captured read-only on cloned state, kit `jevonly-20261104` (`trip.log`).

## Functional requirements

- **FR-1.** A trip's card count is verified when the cards that are not cancelled or completed,
  plus confirmed non-hotel bookings, equal Booking.com's count; the existing all-cards comparison
  still verifies too.
- **FR-2.** Cancelled cards are still read, so cancellations are recorded as before.

## Out of scope

Other incomplete-sync causes.
