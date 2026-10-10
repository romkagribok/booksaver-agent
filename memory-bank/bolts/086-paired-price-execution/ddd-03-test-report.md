---
stage: test
bolt: 086-paired-price-execution
created: "2026-09-27T17:00:00Z"
status: complete
---

# Paired price execution — test report

## 2026-09-27 — construction evidence

`tests/unit/daemon/test_price_comparison_pairing.py` (7):

- For both persisted orders: both arms start from the same snapshot bytes; exactly one history row
  and one savings-pipeline call (baseline); comparison row `scheduled`/`sent`; both arms
  recorded with prices and Jev nano-USD cost; one report to the booking owner with both rows.
- Disabled mode and owner-only mode with an invitee: Jev never constructed, no comparison rows,
  no report, baseline unchanged.
- Shutdown before the Jev arm: `not_run` recorded and reported; baseline unaffected.
- Daily cap and short deadline produce explicit `not_run` arms without browser work.
- Failure report never states "no lower" for the failed arm; cost labels (< $0.0001, upper bound).
- Repository: interrupted pending arms closed, purge removes comparisons.

Schema tests updated for v19. Full suite, Ruff and mypy clean (see release evidence).

Pending (live acceptance, Gate B): native Telegram report for a manual owner check and a scheduled
check after the TypeSafe key is provisioned; multi-day observation (bolts 087/088).

## 2026-09-27 — independent review disposition

A read-only reviewer confirmed disabled mode is unchanged and that the Jev arm writes no canonical
state. Fixed with regressions: unguarded comparison hooks (storage errors now isolated), baseline
exception leaves pair pending (closed as suppressed), job deadline now extended only by actual Jev
run time, second browser skipped after a blocked baseline session, lower-but-non-equivalent price
wording, amount normalization for agreement counts, CLI upper-bound labels. In bolt 085: total
lines with tax/fee/deposit/"from" wording rejected, struck-through prices excluded from the
snapshot, non-en-US number grouping fails closed, "partially refundable"/"no free cancellation"
never grounded as refundable, generic fallback no longer groups rates under a guessed container,
TaskGroup cancels queued sibling calls on first failure, `http.client` errors retried, omitted
zero-probability options accepted, default call cap raised to 100 (worst case 82).
Accepted as known limits: all-or-nothing arm on any provider error; purge can reopen the Jev daily
allowance; invitee inclusion relies on the owner's decision (`participants = "all"`, chosen by the
owner on 2026-09-27) rather than an in-bot TypeSafe disclosure.
Full suite 3,082 passed, 1 skipped; Ruff and mypy clean.

## 2026-10-10 — live acceptance and closure

Native acceptance: the owner confirmed a two-row Telegram report for a manual check on
2026-10-01; scheduled reports were delivered to the owner and to one invitee (56 comparisons, all
with report status `sent`). Only the LLM method wrote history and savings rows throughout
(5 savings alerts, all from baseline results). Criterion disposition:

| Story | Disposition |
|---|---|
| US-209 Pair every eligible price check | Met: manual and scheduled, both arms recorded for all 56 pairs, persisted random order, same session snapshot. |
| US-210 Isolate pair state and recovery | Met: baseline-only canonical effects; comparison steps exception-isolated; interrupted arms closed, never replayed. |
| US-211 Bound pair resources | Met in a different form (ADR-055): the Jev arm's own run time extends the job allowance. **Descoped by owner decision:** shared-inventory cost allocation and the fixed 540 s ceiling (FR-8). |
| US-212 Report two Telegram results | Met for the two-row report. **Descoped by owner decision:** merging/suppressing the separate savings alert and a retrying delivery record (FR-9). |

Paired mode is being retired by ADR-056; its code remains for future comparisons.
Process note: stage documents were written in one pass without per-stage owner stops.
