---
unit: 001-reservation-meal-plan
bolt: 090-reservation-meal-plan
stage: test
status: in-progress
created: "2026-10-10T02:02:11Z"
updated: "2026-10-10T08:07:38Z"
---

# Test Report - Reservation meal plan

## Test Summary

Run on the rebased branch at 2026-10-10T08:02:36Z: `python3 -m ruff check src tests` (clean), `python3 -m mypy
src` (no issues in 133 source files), `python3 -m pytest` (3,226 passed, 1 skipped).

| Category | Passed | Failed | Skipped | Coverage |
|----------|--------|--------|---------|----------|
| Unit | 2,874 | 0 | 1 | not measured |
| Integration | 352 | 0 | 0 | not measured |
| Security | no separate suite | - | - | - |
| Performance | none | - | - | - |
| **Total** | 3,226 | 0 | 1 | not measured |

Coverage was not measured, so the template's 80% target is neither met nor missed on evidence.
The trust rules that would sit in a security suite are unit tests (see "Security Tests").

## Acceptance Criteria Validation

| Story | Criteria | Status |
|-------|----------|--------|
| US-220 | Explicit no-meal row reads `none` with its wording (owner's real desktop example) | ✅ |
| US-220 | Explicit inclusion row reads the included value (inline, next-line, colon forms) | ✅ synthetic wording only |
| US-220 | Unrecognized wording and unranked combinations read `unknown` | ✅ |
| US-220 | Priced-extra wording is not an inclusion | ✅ |
| US-220 | Missing row: `none` with a guest row, `unknown` without it or without the room | ✅ |
| US-220 | A facilities list naming a meal is not meal evidence | ✅ |
| US-220 | Provider-submitted facts cannot set a meal plan | ✅ |
| US-220 | Value and wording stored; value reaches the booking | ✅ |
| US-220 | Stated value kept against `unknown` and silent readings; replaced by a different stated one | ✅ |
| US-220 | Schema v20 migrates to v21 with every meal plan `unknown` | ✅ |
| US-220 | A production reservation that includes breakfast reads `breakfast` | ❌ not yet evidenced; needs the release |
| US-221 | `/bookings` shows the meal plan in plain words | ✅ |
| US-221 | `unknown` shows as "meals not confirmed" | ✅ |
| US-221 | The stored wording is not shown | ✅ |

## Unit Tests

- `tests/unit/test_meal_plan.py` (40): wording classification, including the owner's wording.
- `tests/unit/test_inventory_confirmation_facts.py` (170, of which the meal cases are new):
  labelled, unlabelled, silent, facilities and bounded-text cases.
- `tests/unit/test_grouped_inventory_runtime.py` (124): the parser's value reaches the observed
  reservation; repeated confirmations with different readings stay `unknown`.
- `tests/unit/test_inventory_executor.py` (23): conversion and duplicate merge.
- `tests/unit/telegram/test_commands_readonly.py` (54): the `/bookings` line.

## Integration Tests

`tests/integration/test_account_sync_persistence.py` (19): storage and projection, backfill on
both the agentic and the legacy path, reading precedence, the v20 to v21 migration, and a saved
opportunity surviving the recording of a meal plan. Nine other integration files pin the schema
version and were moved to 21.

## Security Tests

No separate suite. Covered by unit tests: the meal plan reaches a reservation only from the
parser payload; unrecognized unlabelled text is not stored; stored wording is bounded to 200
characters and not shown in `/bookings`.

## Performance Tests

None. The change adds no model call, browser action or page load.

## Coverage Report

Not measured.

## Issues Found

| Issue | Severity | Status |
|-------|----------|--------|
| A bare number or price without a named meal classified as `none` (own review, before the first commit) | Medium | Fixed |
| An inline `Meal Plan` value lost its label before classification, so "Meals are not included" read `unknown` (own review) | Low | Fixed |
| Unrecognized unlabelled text from the room section was stored (own review) | Low | Fixed |
| A facilities list naming a meal could be read as the booked meal plan (Bugbot, head 1e482eb) | Medium | Fixed at 2026-10-10T02:20:12Z |
| "Exclusive" counted as a denial, so inclusion wording containing it read as a stated `none` (Bugbot, head ec4558d) | Medium | Fixed at 2026-10-10T08:02:36Z |
| Any digit beside a named meal counted as a price, so a time or guest count read as a stated `none` (Bugbot, head ec4558d) | Medium | Fixed at 2026-10-10T08:02:36Z: a price needs a currency; "available" and "per person" alone no longer mean `none` |
| `SCHEMA_VERSION` merged cleanly at 20 against PR #78, which would have skipped this migration in production (reported by the session that owns PR #78) | High | Fixed at 2026-10-10T07:49:45Z by moving to v21 |

## Staging evidence

Recorded 2026-10-10T08:03:55Z for source `d19f7b5`, image `booksaver-agent:mealplan-d19f7b5`
(`sha256:3c6438561e70e46e07fa5db48fa2f46380f477f5ef9a93d4eb3c6a19de26302c`), built on the image
then running in production (`jevprimary-7b18adc`).

- Dev, exact image, `--network none`: 133 installed modules match source, dependency pins
  matched, `pip check` clean, daemon and Chromium smoke clean, three supervisor cleanup cases
  confirmed, CLI help.
- Staging, `mealplan_stage_probe.py` on a `sqlite3.backup` copy of the production database,
  `--network none`: schema 20 to 21, integrity ok, zero foreign-key violations before and after,
  all row counts preserved (3 users, 5 bookings, 13 reservations, 230 history rows, 31
  opportunities, 82 comparisons), every existing meal plan unknown, `/bookings` rendered five
  entries with five meal lines for three users, and one existing reservation received a stated
  meal plan with its booking and opportunities kept. The copy was deleted; production stayed at
  schema 20.
- Earlier candidates (1e482eb, aa7be3b on the previous base; ec4558d) passed the same checks and
  are superseded.

## Ready for Operations

- [ ] All acceptance criteria met (one needs the release)
- [ ] Code coverage > 80% (not measured)
- [x] No critical/high severity issues open
- [x] Performance targets met (none apply)
- [x] Security tests passing
- [x] Owner decision on the stage checkpoints (2026-10-10T08:07:38Z: waived after the fact)
- [ ] Bugbot on the final head
- [x] Candidate rebuilt and restaged on the current production base
