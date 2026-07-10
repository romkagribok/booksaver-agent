# ADR-014: Occupancy is a required registration field — no silent default

- **Status**: accepted
- **Date**: 2026-07-05
- **Bolt**: 006-search-journey-monitor (search-journey-monitor)

## Context

A Booking.com search requires party size (adults, children, rooms), and displayed room
prices depend on it. The MVP `Booking` aggregate has no occupancy field because the
manage-page check never searched. Searching with a guessed occupancy (e.g. a hardcoded
"2 adults") could quote a different rate basis than the user actually booked — fabricating
savings that don't exist for their party, or hiding ones that do.

## Decision

`Occupancy(adults >= 1, children >= 0, rooms >= 1)` becomes a **required** part of
registration (user decision at intent-002 Checkpoint 2):

1. `booksaver register` requires `--adults`; `--children` (default 0) and `--rooms`
   (default 1) are explicit, documented CLI defaults — not hidden guesses.
2. Existing bookings are migrated to an explicit *occupancy-missing* state (NULL columns).
   Their checks fail fast with `OCCUPANCY_MISSING` and a message naming the fix; no browser
   is launched.
3. `booksaver bookings set-occupancy <id> --adults N [--children N] [--rooms N]` backfills
   a legacy booking; `bookings list` surfaces occupancy (or `MISSING`).

## Alternatives considered

- **Default to 2 adults / 1 room**: zero-friction migration, but silently wrong for any
  other party — precisely the "silent wrong price" class the intent's reliability NFR
  forbids. Rejected by user.
- **Infer occupancy from the manage page via LLM**: another scraping surface + LLM cost to
  bootstrap a value the user knows offhand; can be added later as a convenience without
  changing this contract.

## Consequences

- One-time friction for existing users (one CLI command per legacy booking), traded for
  price comparisons that are valid for the actual party size.
- Schema v5 adds nullable `occ_*` columns; NULL is reserved exclusively for legacy rows —
  domain code requires occupancy on every new registration.
- Downstream units are unaffected: occupancy participates in *search construction*, not in
  the savings equivalence gate (same property/dates/room/refundable rules as before).
