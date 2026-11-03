---
unit: 001-jev-reservation-facts
bolt: 097-jev-reservation-facts
stage: design
status: complete
created: 2026-11-03T21:24:43Z
updated: 2026-11-03T21:24:43Z
---

# Technical Design - Jev-assisted Reservation Facts

## New module `infrastructure/browser/jev_reservation_facts.py`

- `total_options` / `refund_options`: candidate lines from the normalized page lines; bounded count
  and length.
- `prove_total(lines, index, guests, nights)` and `prove_refund(sentence, check_in, today)`: pure,
  return the same keys the code reader returns (`booked_total`, `currency`, `all_in`;
  `refundability`, `refundability_text`, `refund_deadline`) or None.
- `JevReservationFacts`: one per sync. Asks one question set per page through `TypeSafeClient` with a
  `JevArmMeter` sized to the remaining daily cap and at most 8 pages, applies proven facts, counts
  filled fields, and records its spend as one `jev_price_runs` row (empty `booking_id`, adapter
  `jev-reservation-facts-v1`) so `cost_since` and the cap include it.

## Reader hook

`GroupedInventoryReader` takes an optional async `assist(lines, facts, reasons)`. It runs after the
code parse when the total or refund terms are unknown, before the facts are appended. The reader's
existing deadline and meter still bound the episode. `inventory_confirmation_facts` exposes its line
normalization (`confirmation_lines`) and charge-warning test so both readers share them.

## Wiring

`_make_check_coordinator` builds the assistant when `BOOKSAVER_TYPESAFE_API_KEY` is set and passes it
through `LocalBrowserUseInventoryExecutor` to the reader. The grouped mapping already marks an
explicit total as verified, so proven facts flow through ADR-058 and ADR-059 unchanged.

## Stall extension and limit

`SqliteMonitoringStallRepository.list_upcoming` keys reservations by `account_reservation_id` and
includes never-monitored ones; `is_monitored` already accepts hold reasons. The sync limit becomes
300 seconds.

## Test Plan

Proof functions against the six captured pages and refusal cases; the assistant with a fake client:
asked only when unknown, one set per page, cap respected, errors harmless, privacy of the request;
reader integration; stall extension; then the owner's dad's account on staging.

## Amendment 2026-11-03T21:56:42Z

Implemented as amended in the requirements: code tries all candidates; `JevReservationFacts` calls
Jev only through `_choose_refund` when proven refund terms differ. `charge_warning` became a shared
function with the special-request exemption. Worker-made FR-7 and FR-8 changes: stall rows keyed by
`account_reservation_id` (`reservation_key`); inventory limits validated against
`MAX_INVENTORY_SECONDS = 300`; check-now and scheduled jobs 480 seconds.
