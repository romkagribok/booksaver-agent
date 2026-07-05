---
id: US-017
status: Ready
implemented: false
---

# US-017 Capture occupancy at registration

**Intent:** `002-agentic-search-monitor`
**Unit:** `001-search-journey-monitor`
**Status:** Ready
**Tag:** Phase 2

## Story

**As a** user registering a booking
**I want** to record the booking's real occupancy (adults, children, rooms)
**So that** price checks search Booking.com with exactly my party size and see comparable prices

**Acceptance criteria**

- Given the `register` flow
- When I register a booking
- Then I must provide occupancy: adults ≥ 1, children ≥ 0 (default prompt 0), rooms ≥ 1 (default prompt 1) — invalid values are rejected with a clear message
- And `Booking` carries a required `Occupancy` value object persisted in SQLite
- Given a booking registered before this change
- When the schema migration runs
- Then the booking is marked occupancy-missing (no silent default), its checks fail with a distinct failure code and a message naming the fix
- And a CLI command (e.g. `booksaver bookings set-occupancy <id>`) backfills occupancy, after which checks proceed
- And `bookings list` shows occupancy (or the missing marker)

---
