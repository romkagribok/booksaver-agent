---
unit: 002-meal-aware-offers
bolt: 091-meal-aware-offers
stage: test
status: complete
created: "2026-10-12T22:48:46Z"
updated: "2026-10-13T13:51:32Z"
---

# Test Report - Meal-aware offers

## Test Summary

Run at 2026-10-12T22:48:46Z: `python3 -m ruff check src tests` (clean), `python3 -m mypy src` (no issues in 133
source files), `python3 -m pytest` (3,288 passed, 1 skipped). Coverage was not measured.

| Category | Passed | Failed | Skipped | Coverage |
|----------|--------|--------|---------|----------|
| Unit and integration (whole suite) | 3,288 | 0 | 1 | not measured |
| Security | no separate suite | - | - | - |
| Performance | none | - | - | - |

## Acceptance Criteria Validation

| Story | Criteria | Status |
|-------|----------|--------|
| US-222 | A candidate rate carries a meal plan and the wording it relied on | ✅ wording on the observed offer; classified value on the candidate |
| US-222 | A value code cannot ground is `unknown` | ✅ |
| US-222 | A rate that states nothing about meals is `none` | ✅ Jev by code; model paths by the `none` marker |
| US-222 | Reader matches saved real property pages before production enablement | ❌ descoped (requirements amendment); replaced by the production read-back below |
| US-223 | Offer ranking below the reservation is excluded with its own reason | ✅ |
| US-223 | `unknown` offer excluded when the reservation includes meals | ✅ |
| US-223 | Same or better stays eligible | ✅ |
| US-223 | Reservation `unknown`: no exclusion on meals | ✅ |
| US-223 | All excluded on meals: no equivalent offer, not a failure | ✅ existing conclusive `NO_EQUIVALENT_OFFER`, no terminal diagnosis |
| US-223 | `AGENTS.md` states the amended boundary | ✅ |
| US-224 | Alert states both meal plans | ✅ |
| US-224 | Reservation `unknown`: alert says it could not be confirmed | ✅ |
| US-224 | Saved opportunity re-evaluated once the meal plan is known | ✅ by the existing lifecycle (next conclusive check); no new code, not separately tested here |
| US-225 | Jev reports a grounded meal plan or `unknown` | ✅ |
| US-225 | LLM price path does the same | ✅ Browser Use and legacy extraction. Stagehand reports `unknown` (schema not extended; fails closed) |
| US-225 | Every method passes the same rule | ✅ `select_offer` is called only from the monitor's three selection sites |

## Unit Tests

- `tests/unit/monitor/test_offer_selection.py`: the rule table (11 cases), the reported defect
  (a cheaper room-only rate loses to the breakfast rate), order against currency and
  refundability.
- `tests/unit/test_meal_plan.py`: offer wording to meal plan; same-or-better never ranks `unknown`.
- `tests/unit/monitor/test_agentic_search_check_job.py`: through the monitor, a room-only or
  unread offer for a breakfast reservation ends as `NO_EQUIVALENT_OFFER` with the meal counts and
  no terminal diagnosis; the chosen offer's meal plan reaches the check result.
- `tests/unit/browser/test_jev_price_executor.py`: each offer carries its own rate row's meal
  wording; room-card lines are not meal evidence.
- `tests/unit/test_browser_use_price_executor.py`, `tests/unit/test_browser_executor.py`: the new
  required field travels through the shared mapper and validation.
- `tests/unit/monitor/test_offers_parser.py`, `tests/unit/monitor/test_room_table.py`: legacy
  extraction classifies the wording; the DOM shortcut is not taken for a reservation with meals.
- `tests/unit/savings/test_pipeline.py`: alert lines and both closing sentences.

## Integration Tests

`tests/integration/test_account_sync_persistence.py`: `_migrate_v21` tolerates a column added by
a concurrent start and still raises any other error. No schema change in this bolt.

## Security Tests

No separate suite. Price methods supply wording only and the value is computed by BookSaver; a
missing, `unknown` or unclassifiable value reads `unknown`. The residual risk on the model price
paths (a fabricated inclusion) is recorded in ADR-057's addendum and is not testable offline.

## Performance Tests

None. No model call is added on the Jev or Browser Use path. The legacy path makes its existing
extraction call for reservations that include meals instead of taking the DOM shortcut.

## Coverage Report

Not measured.

## Issues Found

| Issue | Severity | Status |
|-------|----------|--------|
| Seven existing tests pinned the offer shape and failed on the new field | Low | Fixed (fixtures updated) |
| No real rate-table wording is available to qualify the offer reader (FR-11) | Medium | Open. After release the price diagnostic records each candidate's classified meal plan for read-back |
| Legacy path without a model key: a reservation with meals always ends as no equivalent offer | Low | Accepted; fails closed |

## Release evidence

2026-10-12T23:02:04Z: promoted as `mealgate-507aa5b` after Bugbot passed with no findings, dev checks on the
exact image and a staging probe on the real monitored bookings. Healthy, schema 21, no traceback
at start. See `memory-bank/operations/releases/507aa5b-meal-plan-gate.md`. The 24-hour read-back
of the reservation with breakfast is not recorded yet.

## Production read-back (2026-10-13T13:51:32Z)

Read from the production database, read-only, about 15 hours after the release. Production ran
this release for 13 minutes and then image `jevonly-a273c78` (which contains it) with Jev as the
only price method, so every check below used the Jev path.

Reservation with breakfast (paid 101.20 EUR; five alerts at 86 to 87 EUR before the release):

| Check | Accepted rates for the booked room | Selected | Opportunity |
|-------|-------------------------------------|----------|-------------|
| 2026-10-13T03:16Z | one `none` (excluded, `meal_plan_worse`), one `breakfast` | `breakfast`, 114 EUR | none (above the paid price) |
| 2026-10-13T10:52Z | one `none` (excluded, `meal_plan_worse`), one `breakfast` | `breakfast`, 124 EUR | none |

No savings opportunity was created for it after the release.

Two reservations without meals (four checks): the `none` rate for the booked room was selected
and the `breakfast` rate stayed eligible but not selected, so they are unconstrained as designed.

Across the three properties, 26 accepted rates were classified: every one `breakfast` or `none`,
none `unknown`. The wording behind each value is not recorded, so this shows plausible readings,
not page-by-page correctness.

Not observed: the third scheduled check (17:08Z), a production alert with the new wording, and
any check on the Browser Use or legacy path. Container healthy with zero restarts; the only
logged errors were two Telegram network retries.

## Ready for Operations

- [ ] All acceptance criteria met (one descoped; see the requirements amendment)
- [ ] Code coverage > 80% (not measured)
- [x] No critical/high severity issues open
- [x] Performance targets met (none apply)
- [x] Security tests passing
- [x] Owner review of Stages 4 and 5 (2026-10-12T22:56:19Z: approved, with merge and redeploy)
- [x] Bugbot, staging and release evidence
- [x] Production read-back (about 15 of the 24 hours; the owner closed the intent on 2026-10-13T13:51:32Z)
