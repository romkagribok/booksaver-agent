---
unit: 001-jev-reservation-facts
bolt: 097-jev-reservation-facts
stage: test
status: complete
created: 2026-11-03T21:56:42Z
updated: 2026-11-03T21:56:42Z
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
