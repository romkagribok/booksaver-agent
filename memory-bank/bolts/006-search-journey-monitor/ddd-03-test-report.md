---
unit: 001-search-journey-monitor
bolt: 006-search-journey-monitor
stage: test
status: complete
updated: 2026-07-06T00:05:00Z
---

# Test Report — Search Journey Monitor

## Summary

| Metric | Value |
|--------|-------|
| Total tests | **277 passed, 0 failed** |
| New in this bolt | 66 |
| Pre-existing (regression surface) | 211 — all green, savings/notifications/rebook untouched |
| Lint (`ruff check src/`) | clean |
| Types (`mypy src/`) | clean (48 files) |

## New Test Coverage by Story

### US-017 — Occupancy (16 tests)
- `tests/unit/test_occupancy.py` (6): validation bounds (adults ≥ 1, children ≥ 0,
  rooms ≥ 1), defaults, CLI display format.
- `tests/integration/test_occupancy_persistence.py` (6): registration round trip;
  DB CHECK rejects invalid occupancy; **v4 → v5 migration** on a hand-built v4 database
  (legacy row hydrates `occupancy=None`, old check rows survive the table rebuild, the
  rebuilt table accepts `extraction_method='agent'`, reopen is idempotent);
  `set_occupancy` backfill + unknown-id `KeyError`.
- `tests/unit/monitor/test_search_check_job.py::TestOccupancyGuard` +
  `test_mixed_bookings_one_missing_occupancy`: `OCCUPANCY_MISSING` failure emitted
  *without any browser action*, with the fix command in the detail; other bookings
  in the same run unaffected.
- Updated fixtures: `test_services.py`, `test_persistence.py` register with occupancy.

### US-018 — Scripted search journey (14 tests)
- `tests/unit/monitor/test_search_journey.py`: happy path executes all 8 steps in
  order; property matched by normalized name; dates + property name used in search;
  per-step failure mapping (`NAVIGATION_ERROR`, `STEP_FAILED` with step name + selector
  detail, `PROPERTY_NOT_FOUND`); `verify_context` rejects wrong dates and wrong
  occupancy; captcha → `BOT_WALL` (also takes priority over step codes); signed-out
  page → `AUTH_REQUIRED`; consent banner clicked when present, absent overlays never
  fail the step.

### US-019 — Extraction, selection, savings integration (36 tests)
- `tests/unit/monitor/test_room_table.py` (9): DOM block parsing (label, all-in total,
  refundability wording), exact-match-only confidence, unknown refundability, no-price
  blocks skipped, confident-exact-match happy-path gate.
- `tests/unit/monitor/test_offer_selection.py` (11): every exclusion rule
  (non-refundable, refundability-unknown, room mismatch, low confidence with 0.5
  threshold boundary, currency mismatch), cheapest-survivor selection, cheaper-but-
  excluded loses, empty selection, exclusion summary.
- `tests/unit/monitor/test_offers_parser.py` (8): LLM offers JSON parsing — valid
  array, no/malformed/non-list JSON → empty (never a guess), bad price skipped,
  missing label skipped, out-of-range confidence → 0.0, non-bool refundability → None.
- `tests/unit/monitor/test_search_check_job.py` (remaining): DOM exact match succeeds
  with **zero LLM calls**; success flows through the *real* `detect_savings` and yields
  a `SavingsOpportunity` (50.00 EUR on the fixture); verified fields echo the booking;
  drift match uses exactly 1 LLM call, emits `room_label=None`, and still passes the
  US-008 gate; `EXTRACTION_FAILED` vs `NO_EQUIVALENT_OFFER` distinction; LLM error
  degrades to DOM candidates; `run_all_active` session handling (no session →
  `AUTH_REQUIRED` per booking, refreshed cookies persisted).

## Regression Statement (FR-5)

Savings detection, notifications, and guided rebook were not modified; their 211
pre-existing tests pass unchanged. The monitor emits the same `CheckResult` contract —
verified by feeding monitor output directly into `detect_savings` in tests.

## Not Covered (accepted)

- Live Booking.com selectors (`_SEL_*`) are unverifiable in unit tests by design;
  drift lands on named-step failures and is bolt 007's escalation trigger.
- `PlaywrightInteractiveBrowser` is exercised only via its port contract (real browser
  runs happen in operations verification, as with bolt 003's adapter).
