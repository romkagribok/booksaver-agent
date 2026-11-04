---
unit: 001-jev-reservation-facts
bolt: 097-jev-reservation-facts
stage: test
status: complete
created: 2026-11-03T21:56:42Z
updated: 2026-11-04T00:26:40Z
---

# Test Report - Jev-assisted Reservation Facts

## Summary

- Full suite: 3,370 passed, 1 skipped, 52 existing warnings; Ruff clean; mypy clean (136 modules);
  AI-DLC validators 0 errors.
- Unit tests use the shapes of the owner's dad's real pages with names replaced: converted and
  single-guest totals, every refusal case, refund proofs and refusals, the assistant's privacy
  (no name, confirmation number, amount or unproven sentence sent), cap, page limit and errors.

## Live replay on the candidate (kit `jevfacts-20261103`, daemon paused, cloned database)

| Reservation | Before | After |
|---|---|---|
| Dad: AIRINN Nov 10 | refund and total unknown | non-refundable, EUR 122 (not monitored, correct) |
| Dad: Aloft Nov 11 | non-refundable, total unknown | non-refundable, USD 150.89 |
| Dad: Best Western Nov 12 | total unknown | eligible, USD 521.11, deadline Nov 11 |
| Dad: Hampton Nov 12 | total unknown | eligible, USD 577.42, deadline Nov 7 |
| Dad: AIRINN Nov 17 | total unknown | eligible, EUR 102, deadline Nov 17 |
| Dad: Kalipè Jan 27 | refund unknown | eligible, EUR 701, deadline Jan 23 |
| Owner: Union Club (rebooked) | total unknown | eligible, USD 592.48 |

Both syncs completed with no unknown facts. Jev was not called: no page proved two refund terms.
An earlier candidate (before the amendment) asked Jev twice for USD 0.00005 and still left the
Hampton total and the AIRINN Nov 10 terms unknown, which is what led to the amendment.

## Not covered live

A page proving two different refund terms (Jev's tie-break) has only unit tests.

## Redesign test (2026-11-04T00:26:40Z): Jev reads, code wins where it reads

- Full suite 3,377 passed, 1 skipped; Ruff and mypy clean. New tests: candidates carry no personal
  data; the total must be the largest amount in its currency; deadlines from dates or "within ..."
  with the 14-hour margin; two agreeing confident answers required; code facts stand and
  disagreements are counted; cap and two-calls-per-page limits; one owner notice per day; cut-off
  calls charged; Jev totals fill but never replace a saved total and never conflict; schema v23
  migration; the alert label; the grouped mapping marks Jev totals unverified.
- Reliability measurement before the redesign (owner's and dad's 7 pages, 3 runs each): total 21/21,
  refundability 21/21, consistent; tax inclusion unreliable, so it is not asked.
- Live replay on the candidate (schema 23): dad 6 of 6 and owner 1 of 1 correct. Jev filled 6 totals
  and 2 refund terms, agreed with the code reader on all 6 facts both read, no disagreement.
  12 + 2 Jev calls cost USD 0.00078. Sources stored: `jev` for six totals, `code` for one.
- Not covered by a dedicated test: forcing `booked_total_source = "code"` on the provider
  submission path (one-line mapping).

