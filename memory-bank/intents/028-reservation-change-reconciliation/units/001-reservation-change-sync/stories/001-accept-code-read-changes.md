---
id: 001-accept-code-read-changes
unit: 001-reservation-change-sync
intent: 028-reservation-change-reconciliation
status: complete
priority: must
created: "2026-11-02T20:51:19Z"
assigned_bolt: 093-reservation-change-sync
implemented: true
---

# US-233: Accept code-read reservation changes

## User story

As a BookSaver user, I want a reservation I changed in Booking.com to update automatically, so that it keeps being monitored.

## Assigned requirement

FR-1, FR-5.

## Acceptance criteria

- [ ] Given a code-read observation with the same confirmation and hotel and different dates, when it syncs, then the reservation and booking take the new dates and the run succeeds.
- [ ] Given a code-read change of refund deadline, refundability, room or occupancy, when it syncs, then that fact updates.
- [ ] Given a provider-submitted observation with different facts, when it syncs, then it still fails closed with `persistence_conflict`.
- [ ] Given a code-read observation with only one stay date, when it differs, then it fails closed.
- [ ] Given any accepted change, when it commits, then the booking's saved opportunities are gone and its check history is kept.

## Out of scope

A new-confirmation rebook.
