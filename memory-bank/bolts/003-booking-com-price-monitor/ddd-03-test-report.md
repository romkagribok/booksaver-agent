---
unit: 002-booking-com-price-monitor
bolt: 003-booking-com-price-monitor
stage: test
status: complete
updated: 2026-07-05T00:00:00Z
---

# Test Report — Booking.com Price Monitor

## Summary

**136/136 tests passing** (55 new for this bolt, 81 pre-existing). Ruff clean,
mypy strict clean across 35 source files.

## New test coverage (55 tests)

### `tests/unit/monitor/test_check_job.py` (14)
- `booking_url` resolution (URL ref vs manage-page fallback)
- DOM extraction success path with refund indicators (US-005/US-006)
- Navigation failure → `navigation_error` CheckResult, never raises (US-014)
- Unauthenticated page → `auth_required` (US-004)
- LLM fallback invoked only when DOM misses (US-006)
- LLM exception degrades to `extraction_failed` without crashing (US-006/US-014)
- DOM-only mode when no LLM configured (US-006 graceful degradation)
- `run_all_active`: per-booking history records, missing-session auth failures without
  navigation, refreshed-cookie persistence, reauth flagging, empty-list no-op

### `tests/unit/monitor/test_session_and_failures.py` (14)
- SessionManager: valid/missing/reauth-required/expired session handling; expiry
  transition persisted (US-004)
- SessionState expiry semantics
- FailureTracker: threshold warning, once-per-streak dedup, success reset,
  invalid threshold rejected (US-014)

### `tests/unit/monitor/test_extraction.py` (15)
- DOM: EUR symbol/code formats, European decimal style, total-context requirement,
  refundable/non-refundable/unknown hints, empty page
- LLM reply parsing: clean JSON, JSON-in-prose, no JSON, malformed JSON, null fields,
  invalid currency rejection, out-of-range confidence clamping

### `tests/integration/test_check_history.py` (12)
- SqliteCheckHistoryRepository: full success/failure round-trips, newest-first ordering
  with limit, consecutive-failure counting, FK enforcement against unknown bookings
- Schema migration: hand-built v1 database migrates to v2 (stub dropped, full columns
  usable, version rows [1, 2]); fresh database lands on v2 directly
- LocalSessionRepository: round-trip, missing file, corrupt file → None, 0600 permissions

## Not covered (by design)

- `PlaywrightBrowserSession` and `AnthropicExtractor` network paths — these adapters are
  thin wrappers over third-party SDKs and require a live browser / API key. The parsing
  logic they feed (`dom_extract`, `parse_extraction_response`) is fully unit-tested.
  Manual verification: `booksaver auth` + `booksaver run` against a real booking.

## Issues found during testing

None — all 55 new tests passed on first run after implementation.

## Commands

```bash
python3 -m pytest            # 136 passed
python3 -m ruff check src/ tests/   # clean
python3 -m mypy src/         # strict, clean
```
