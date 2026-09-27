---
stage: technical-design
bolt: 086-paired-price-execution
created: "2026-09-27T17:00:00Z"
status: complete
---

# Paired price execution — technical design

## Flow (`CheckCoordinator._run_booking`)

Shared preflight (session resolution, active user) is unchanged and not a paired observation.
Then, when `[jev_comparison] enabled`, a TypeSafe key is present, the booking has occupancy and
`participants` admits the user:

1. Persist the comparison and two pending arms with a `SystemRandom` first arm.
2. Jev-first: run the Jev arm (fresh lease from the **same** `snapshot.cookies`), persist it,
   restart the baseline's phase clock.
3. Run the existing method unchanged (`_run_booking_price`, the former body) with all canonical
   effects.
4. Baseline-first: run the Jev arm afterwards from the original snapshot bytes (never the
   refreshed session).
5. Persist both arms, format one report, send it to the booking owner's chat (recipient access
   rechecked), record `sent|failed|suppressed`.

Both arms run sequentially in the coordinator thread under the existing execution gate, each in
its own transient browser. Shutdown or revoked access before the Jev arm records `not_run`.

## Limits

- Jev arm: `min(job deadline, now + arm_timeout_seconds)`, 15 actions, 0 visual actions,
  `max_calls_per_arm`, remaining daily cap as its spend envelope; < 30 s left or cap reached →
  `not_run` with reason.
- The job allowance stays 2×180 s; each Jev arm's actual run time is added to it afterwards, so
  the baseline keeps its unpaired time (ADR-055). The daily check counter is incremented once per
  logical pair. Compose `stop_grace_period` 360 s.
- If the baseline ran first and ended in `auth_required` or `bot_wall`, the Jev arm is recorded
  `not_run/baseline_blocked` instead of opening a second browser on that session.
- Every comparison step is exception-isolated: a comparison failure is logged and can never change
  the canonical check; a baseline exception closes the pair (`suppressed`) and still propagates.

## Persistence

Schema v19 (additive): `price_comparisons`, `price_comparison_arms` (FK cascade). User purge
and booking deletion remove them explicitly. Pending arms older than 20 minutes are closed as
`failure/interrupted` at the next comparison start — never replayed.

## Reporting

One plain-text Telegram message per booking check with two labelled rows (price or bounded failure
reason, comparison with the booked price, AI cost with "< $0.0001"/"upper bound" labels, elapsed
seconds, model calls), order, start gap and reference. CLI: `booksaver comparison report [--days N]`.

## Plan departures (first functional pass, owner-requested speed)

- The existing savings alert is **not** suppressed/merged; the comparison report is an extra
  message. Delivery is one attempt with a recorded status (no retry outbox).
- Invitee inclusion is an owner config switch (`participants`), not a new in-bot TypeSafe consent
  flow; the default is owner-only.
- Shared inventory cost is not allocated/shown per pair; both arms' costs are method-only.
