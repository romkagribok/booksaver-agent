---
unit: 003-savings-detection-notifications
bolt: 004-savings-detection-notifications
stage: test
status: complete
updated: 2026-07-05T00:00:00Z
---

# Test Report — Savings Detection & Notifications

## Summary

**168/168 tests passing** (32 new for this bolt). Ruff clean, mypy strict clean
across 40 source files.

## New test coverage (32 tests)

### `tests/unit/savings/test_savings_detection.py` (17)
- **Equivalence gate matrix (US-008)**: no-contradiction pass, matching-fields pass,
  case-insensitive property/room match, check-in/check-out mismatch rejection,
  property mismatch, room mismatch, `not_refundable` rejection, `refundability_unknown`
  rejection (both `is_refundable=None` and missing indicators)
- **Price rule (US-007)**: cheaper detected with correct amount + percent (12.50%),
  equal rejected, higher rejected, one-cent-cheaper detected, currency mismatch
  rejected, gate-over-price priority (cheap but non-refundable → rejected),
  failed-check input raises, percent rounding to 2dp

### `tests/unit/savings/test_pipeline.py` (11)
- **Channel independence (US-009)**: both channels alerted; one failing doesn't block
  the other; all failing leaves opportunity persisted but unnotified; zero channels
  still persists
- **Alert content (US-009)**: baseline/live/saved/percent/confirmation-id present,
  `booksaver rebook <id>` pointer included, explicit-confirmation promise present
- **Pipeline flow**: failed checks skipped, rejected offers silent, unknown booking
  skipped, multiple results processed independently

### `tests/integration/test_savings_repo.py` (4)
- SQLite round-trip (all Money/Decimal fields), `mark_notified` persistence,
  per-booking + global listing, unknown id → None

### Migration tests updated
- Version-chain test now asserts v1 → [1, 2, 3]; fresh DB lands on `SCHEMA_VERSION`
  directly (no hard-coded version numbers going forward).

## Issues found during testing

- Two E501 lint violations in test file — reformatted. No functional issues; all new
  tests passed on first run.

## Commands

```bash
python3 -m pytest            # 168 passed
python3 -m ruff check src/ tests/   # clean
python3 -m mypy src/         # strict, clean
```
