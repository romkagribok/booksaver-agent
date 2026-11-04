---
unit: 001-jev-reservation-reader
bolt: 098-jev-reservation-reader
stage: test
status: complete
created: 2026-11-04T15:47:58Z
updated: 2026-11-04T15:47:58Z
---

# Test Report - Jev Reservation Reader

## Summary

- Full suite 3,260 passed, 1 skipped (the drop is removed parser tests: 31 failing and 86 trivially
  passing cases deleted, 6 adjusted); Ruff and mypy clean; AI-DLC validators 0 errors.
- Net change: about 1,040 lines removed, 126 added.
- Jev module tests: reading, exact deadline from a dated cost line, calendar months, replacement of
  earlier facts, unagreed/unconfident/failed answers keep facts and record a reason, cap and call
  limits, cut-off calls charged. Reconciliation: a Jev total fills or replaces a saved total; an
  unverified total still conflicts.

## Live replay (kit `jevonly-20261104`, cloned data, daemon paused)

All seven reservations correct: dad's four refundable stays eligible (Kalipè now included), both
non-refundable stays non-refundable, owner's stay eligible at USD 592.48 with deadline 2027-04-12.
AIRINN Nov 17's deadline reads 2026-11-16 from "within 13 days ..." less the 14-hour margin, one day
before the page's own date; this errs early. One refund answer was unread in the dad's sync and the
saved value was kept (FR-6). Jev cost USD 0.0008 for seven pages.
