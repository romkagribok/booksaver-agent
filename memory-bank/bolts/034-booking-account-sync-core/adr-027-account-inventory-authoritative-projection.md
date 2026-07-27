---
id: ADR-027
title: Booking.com account inventory is authoritative
status: accepted
created: 2026-07-27T16:33:44Z
bolt: 034-booking-account-sync-core
---

# ADR-027: Booking.com Account Inventory Is Authoritative

## Context

BookSaver previously treated manually entered local booking aggregates as authoritative. Authenticated
per-user Booking.com sessions now make those facts observable from their real source, while manual
registration/edit/delete and post-rebook detail dialogs create conflicting state.

The existing strict `Booking` aggregate remains valuable to the mature current-price search and
savings pipeline because it requires complete property, dates, room, occupancy, refundable policy,
and baseline money.

## Decision

Persist every observed hotel reservation in a synchronized account-inventory model. Booking.com is
authoritative for identity, booked facts, and lifecycle. Users cannot mutate these local snapshots.

Create or update the existing strict `Booking` aggregate only as a derived monitoring projection for
an eligible synchronized reservation. Reconciliation is its only writer. Ineligible reservations
remain visible in account inventory without weakening `Booking` invariants.

Remove manual booking CRUD and guided rebooking. Users perform all reservation actions directly in
Booking.com; later synchronization observes distinct remote reservations independently.

## Rationale

- One external authority eliminates duplicate entry and stale manual correction.
- A separate inventory model can represent incomplete, cancelled, past, and ineligible records.
- Retaining the strict projection minimizes risk to established equivalence/search/savings logic.
- Read-only monitoring is simpler and preserves the strongest human-action boundary.

## Consequences

- Schema v11 adds synchronized inventory/run data and removes legacy booking-scoped data.
- Every check requires a current conclusive synchronization.
- `/bookings` becomes an account inventory view.
- Similar old/new reservations are not merged or treated as replacements.
- Existing rebook state machine and manual booking commands are retired.
