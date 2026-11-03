---
unit: 001-reservation-change-sync
bolt: 093-reservation-change-sync
stage: design
status: complete
created: 2026-11-03T00:49:01Z
updated: 2026-11-03T00:49:01Z
---

# Technical Design - Reservation Change Sync

## Reader (`inventory_confirmation_facts._price_facts`)

If the line after `(for N guests)` is `approx. <money>`, remove it and remember it, then use the
existing statement-free path. A converted block requires no final-price statement, a currency
different from the total, rows in the conversion's currency, a VAT/TAX row within 1 of rate times
room, and a sum within 1 of the conversion. City tax rows are not accepted in this shape because
none was observed. Every other existing check still runs.

## Provenance (`stay_facts_verified`)

A new flag next to `booked_total_verified` on `ObservedReservation` and `ReservationObservation`.
Only the grouped reader sets it. Duplicate merging ANDs it; the observation mapper copies it.

## Persistence (`sqlite_store`)

`_agentic_observation_conflicts` skips check-in, check-out, room, refund deadline, occupancy and
refundability when the flag is set and both dates are present. Confirmation, hotel, lifecycle and
unverified-total rules stay. `_merge_agentic_existing_observation` takes the observed values and,
when dates, room or occupancy changed, clears any total or refund fact not re-read. The existing
eligibility path then archives a held reservation and `_upsert_projection` reactivates the same
booking and removes opportunities when facts change. No schema change.

## Test Plan

Reader fixtures for the observed shape and each rejection; persistence tests for each changed fact,
hold, release from hold, unverified rejection, one date only, opportunities and history; a grouped
runtime test for the flag; a replay of the owner's sync on staging.
