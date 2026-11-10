---
stage: plan
bolt: 111-total-in-booking-currency
created: 2026-11-10T13:26:27Z
---

# Implementation Plan

- `JevReservationFacts`: add `booking_currency` (options: the distinct currencies in the price
  area, "not_stated"); total question `not_for` adds "an approximate amount converted into another
  currency for display". Apply the total only when `check_total`'s currency equals the agreed
  currency (when one is agreed; single-currency pages need no answer beyond agreement).
- Bump the adapter to `jev-reservation-facts-v5`.
- Unit tests; offline Jev on the captured Ayres, Aloft and AIRINN pages; staged sync and Ayres check.
