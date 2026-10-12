---
unit: 013-confirmation-booked-total
bolt: 092-confirmation-booked-total
stage: test
status: complete
created: 2026-10-10T02:05:01Z
updated: 2026-10-12T22:18:02Z
---

# Test Report - Confirmation Booked Total

## Summary

- Final source (main 108bc23 plus this work), 2026-10-12T22:14Z (minute precision):
  **3,257 passed**, 1 skipped, 52 existing warnings (`python3 -m pytest -q`); Ruff clean; mypy
  clean for 133 source modules.
- AI-DLC artifact and status validation: 0 errors, 0 inconsistencies, 471 historical warnings.
- Affected-caller replay on the real confirmation page: **passed** on the fourth attempt, after
  the reader was corrected from what the second and third attempts showed. Details below.
- Coverage was not measured; the repository gate has no coverage run.
- Earlier runs, kept for the record: 3,125 passed on 2026-10-10 before the rebase; 3,259 passed
  on 2026-10-12 after the rebase and before the layout correction (the dollar tests were then
  rewritten, which changed the count).

## Affected-caller replay

Method: candidate image built on the production host from the uncommitted source on the current
production base; production daemon stopped; data volume mounted read-only; state cloned to a
temporary directory; Telegram delivery disabled; the caller's normal coordinator inventory
refresh run once; production restarted on its original image and checked healthy. Kit:
`/opt/booksaver-releases/bookedtotal-20261012`.

1. 22:00:20Z–22:00:57Z, image `bookedtotal-wip-9a45af6`: probe import error, no page was loaded.
2. 22:08:22Z–22:09:54Z, same image: refresh complete; refund deadline 2026-11-21 read from the
   refund schedule; total still USD301 with diagnostic `booked_total:final_price_statement`.
3. 22:10:23Z–22:11:50Z, same image plus a one-off capture of the owner's price block: showed
   `US$` amounts and a total closed by `Additional Info` with no final-price statement.
4. 22:15:36Z–22:17:07Z, image `bookedtotal-wip-0478f4c` (corrected reader, capture removed):
   refresh complete, 1 discovered, 1 eligible, `unknown_facts` empty. Saved USD301 became
   USD346.08 on the reservation and on the same monitoring booking (`59d6823f`), its 92 checks
   kept, refund deadline 2026-11-21, still eligible. Other callers: 12 rows, revision sum 31,
   identical before and after.

After each attempt production ran its original image `3c6438561e70`, healthy, and the production
row still read USD301: nothing was written outside the discarded clone. Total production pause
across the four attempts was about five minutes; no scheduled check was due in that window.

Limits: the replay candidates are work-in-progress images built from uncommitted source, not the
image that will be released. The replay covers one caller, one reservation and one layout.
Attempt 3's log contains the captured price lines of the owner's own page and is kept root-only.

## Tests added or changed

- `tests/unit/test_inventory_confirmation_facts.py`: dollar layout shaped from the real page;
  pound, `US$`, CAD and PLN variants of the euro page; grouped thousands; sixteen named rejection
  reasons including a bare dollar sign, comma decimals, mixed currency, wrong tax arithmetic, an
  unrecognized component row, an unproven tax-inclusive total and each refund schedule failure;
  cost tiers in two currencies; label beside or above the sentence; expired schedule; cost tiers
  outranking the sentence; a euro page without its statement; reasons free of page content.
- `tests/unit/test_grouped_inventory_reader.py`: reasons counted as fixed codes in the coverage
  diagnostic without page content.
- `tests/unit/test_grouped_inventory_runtime.py`: a reconciled total is marked page-verified; a
  confirmation without a total is not.
- `tests/integration/test_agentic_inventory_persistence.py`: a page-verified USD346.08 replaces a
  saved USD301 on the reservation and the booking, keeps identity and removes the stale savings
  opportunity; the same change without the marker fails closed and changes nothing.

The 150 pre-existing confirmation reader tests pass unmodified, as do the meal-plan tests merged
from main.

## Acceptance Criteria Validation

### US-226: Record the confirmation total in its printed currency

- ✅ Recognized prefixed symbols and ISO codes reported as the printed currency; euro unchanged.
- ✅ en-US grouping only; other grouping, an unrecognized token or a bare dollar sign is not money.
- ✅ Room, VAT/TAX, city-tax and additional-charge rows share the currency and reconcile.
- ✅ Statement-free layout needs the `Additional Info` close and a reconciled tax row.
- ✅ Cost tiers in one currency, or the exact refund schedule sentence when no tier is rendered.
- ✅ Property-timezone caution shared by both cancellation sources.
- ✅ No conversion; no page content in product logs or diagnostics.
- ✅ Confirmed on the real page (attempt 4).

### US-227: Replace a stale saved total with the page-verified total

- ✅ Marker set only by the grouped reader with an explicit all-in total; merges need both sides.
- ✅ Replacement updates reservation and booking in one reconciliation, same identity.
- ✅ Stale savings opportunity removed; kept when an unverified change is rejected.
- ✅ Unverified differing total fails closed without changes.
- ✅ Other saved-fact rules and other callers unchanged; confirmed on the real replay.

### US-228: Qualify the confirmation total for the affected caller

- ✅ Deterministic positive and negative tests.
- ✅ Content-free reason codes recorded; they identified the failing rule on the real page.
- ✅ Isolated replay shows USD301 replaced by USD346.08 with the booking still eligible.
- ✅ Full test, Ruff, mypy and AI-DLC gates run and recorded.

## Issues Found

- The first implementation was written before any AI-DLC record existed; it was removed and
  redone in order. Recorded in the inception and construction logs.
- The dollar layout assumed from a screenshot was wrong in two respects (no final-price
  statement, `US$` prefix). The diagnostic added for US-228 named the rule, the design was
  amended first, and the reader was corrected.
- The operator probe had an import-path fault and my first wait loop matched its own command
  line; both were in the replay tooling, not in product code.

## Recommendations

- After release, read the `unknown_facts` diagnostic for the invitee's two unmonitored
  reservations; this bolt may fix them (a euro page without its statement now qualifies) but
  that was not observed.
- Operations still owes: commit and review, Bugbot on the final head, an exact-image build from
  the committed source with Development and Staging checks, promotion, and a release record.
