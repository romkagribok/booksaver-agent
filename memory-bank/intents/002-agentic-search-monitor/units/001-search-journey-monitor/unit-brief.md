# Unit Brief: Search Journey Monitor

**Unit ID:** `001-search-journey-monitor`
**Intent:** `002-agentic-search-monitor`
**Status:** Planned
**Build order:** 1

## Purpose

Replace the manage-page price check with a scripted full search journey: search Booking.com for the
registered property with the exact dates and the booking's real occupancy, verify the property's
identity in the results, open its page, extract equivalent refundable offers with their all-in
bookable totals, and emit the cheapest as a `CheckResult` for the existing savings pipeline. Adds the
required `Occupancy` value object to registration with a migration path for existing bookings. LLM is
used here only for judgment (room-type match, refundability wording) — the browser-agent escalation is
Unit 2.

## Dependencies on other units

| Unit | What this unit needs |
|------|----------------------|
| intent-001 `001-core-local-data` | `Booking` aggregate + registration flow (extended with `Occupancy`), SQLite schema migration, config |
| intent-001 `002-booking-com-price-monitor` | Browser port, session manager, failure tracker, `CheckResult` shape, check-history repository |
| intent-001 `003-savings-detection-notifications` | Consumes the emitted `CheckResult` unchanged — its equivalence gate and tests must keep passing |

## Downstream consumers

- Unit 2 (`002-agentic-escalation`) wraps each journey step with an escalation point.
- Savings detection / notifications / rebook (intent 001) consume results unchanged.

## Loose coupling / interfaces (design-level)

| Consumes | From |
|----------|------|
| `Booking` (+ new `Occupancy`) | core-local-data |
| `BrowserSession` port, `SessionManager` | price-monitor |
| `LLMExtractor` (judgment calls) | price-monitor |

| Emits | To |
|-------|-----|
| `CheckResult` (success: live all-in total, refund indicators, extraction method; failure: coded reason) | savings pipeline, check history |
| Journey step outcomes (step name, success/failure, reason) | Unit 2 escalation + traces |

## Recommended implementation order (within unit)

1. US-017 — Occupancy at registration + migration + CLI backfill
2. US-018 — Scripted search journey to verified property page
3. US-019 — Equivalent-offer extraction and savings-pipeline integration

---

## Story Files

- `US-017`
- `US-018`
- `US-019`

## Cross-cutting constraint

US-013 (local-only) applies; the journey is read-only on the account.

---

## Completion criteria (unit-level)

- Registration requires occupancy; migrated bookings without it fail checks with a clear message and
  can be backfilled via CLI.
- On schedule, the daemon completes search → results → verified property page → room table using the
  saved session, without deep-linking.
- Cheapest equivalent refundable offer (all-in total) becomes a `CheckResult`; existing savings,
  notification, and rebook tests pass unchanged.
- Manage page no longer used as a price source.
