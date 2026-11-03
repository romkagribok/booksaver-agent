---
id: 002-clear-stale-facts-and-hold
unit: 001-reservation-change-sync
intent: 028-reservation-change-reconciliation
status: complete
priority: must
created: "2026-11-02T20:51:19Z"
assigned_bolt: 093-reservation-change-sync
implemented: true
---

# US-234: Clear stale facts and hold

## User story

As a BookSaver user, I want no alert based on my old total, so that a reported saving is real.

## Assigned requirement

FR-2, FR-4.

## Acceptance criteria

- [ ] Given changed dates and an unverified total, when it syncs, then the saved total is cleared and the reservation is ineligible with `MISSING_BOOKED_TOTAL`.
- [ ] Given changed dates and unread refund facts, when it syncs, then they are cleared and the reservation is ineligible.
- [ ] Given a held reservation, when a scheduled run happens, then no savings alert can be sent.
- [ ] Given a held reservation, when a later sync verifies the total, then the same booking is active and checked again.
- [ ] Given unchanged dates and an unverified total, when it syncs, then the saved total stays, as today.

## Out of scope

Asking the user for a total.
