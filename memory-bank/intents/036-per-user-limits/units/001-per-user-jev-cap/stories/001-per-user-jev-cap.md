---
id: 001-per-user-jev-cap
unit: 001-per-user-jev-cap
intent: 036-per-user-limits
status: complete
priority: must
created: "2026-11-10T00:46:00Z"
assigned_bolt: 107-per-user-jev-cap
implemented: true
---

# US-259: Each user has their own Jev daily cap and a check limit that fits their bookings

## User story

As a BookSaver user with several bookings, I want every booking checked every day and my checks never
stopped by someone else's usage, so that I don't miss a price drop.

## Assigned requirement

FR-1 to FR-3.

## Acceptance criteria

- [x] Given another user spent the whole cap today, when my price check runs, then it runs with my full allowance.
- [x] Given I spent the whole cap today, when my price check runs, then it is refused with `daily_cost_limit`.
- [x] Given another user spent the whole cap today, when my sync reads reservation facts, then Jev gets my full allowance.
- [x] Given the spend ledger cannot be read, when a Jev run starts, then it is refused.
- [x] Given no `[limits]` setting, when config loads, then `max_checks_per_user_per_day` is 150.

## Out of scope

`max_bookings_per_user` enforcement.
