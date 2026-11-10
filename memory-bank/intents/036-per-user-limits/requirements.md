---
intent: 036-per-user-limits
phase: construction
status: complete
created: "2026-11-10T00:46:00Z"
updated: "2026-11-10T00:46:00Z"
---

# Requirements: Per-user limits sized for real bookings

## Intent overview

On 2026-11-09 user 4 (`smarchuk`) was told "daily check limit reached": five active bookings at three
scheduled checks each need 15 checks, and production allowed 12 per user. The 19:02 UTC slot skipped
three bookings with `user_check_limit_reached`. Claude is no longer used anywhere, so the only spend is
Jev (TypeSafe), about USD 0.001 per run (USD 0.002 to 0.024 a day over the week before). The per-user
check limit and the Jev daily cap exist only to stop a runaway loop or a deliberate drain. The Jev cap
is currently one USD 0.25 total shared by every user, so one user's loop would stop everyone's checks.

## Functional requirements

- **FR-1.** The Jev daily cost cap applies per user: each user's Jev spend since UTC midnight (price
  runs, reservation-facts runs and historical comparison arms) is measured against
  `max_daily_cost_usd` on its own; one user's spend never reduces another user's allowance. The amount
  stays USD 0.25 by default and at most USD 1.00.
- **FR-2.** An unreadable spend ledger still refuses the run (fail closed), as today.
- **FR-3.** The default `max_checks_per_user_per_day` is 150 (50 bookings at three checks a day), in
  code, `config.toml.example` and the `init` template, matching production.

## Out of scope

Enforcing `max_bookings_per_user` (configured but never enforced; owner to decide); persisting the
in-memory check counter across restarts; changing `messages_per_minute_per_chat`.
