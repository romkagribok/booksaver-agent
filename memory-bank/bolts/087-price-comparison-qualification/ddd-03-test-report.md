---
stage: test
bolt: 087-price-comparison-qualification
created: "2026-10-10T01:48:15Z"
status: complete
---

# Paired price comparison — decision report

Production data read at 2026-10-10T01:46Z. Cohort `jev-price-v2:jev-1.13.0`, 82 pairs from
2026-10-01T05:40Z to 2026-10-10T01:18Z (81 scheduled, 1 manual; LLM method first in 43, Jev first
in 39; all 82 reports delivered). Three bookings, two users.

## Overall

| | LLM method (Browser Use + Claude) | Jev |
|---|---|---|
| Verified a price | 37 of 82 (45%) | 53 of 82 (65%) |
| Model cost | USD 17.71 | USD 0.115 |
| Cost per verified price | USD 0.479 | USD 0.0022 |
| Average seconds per run | 81.1 | 31.2 |
| Runs with estimated (not exact) cost | 0 | 0 |

Both verified in 31 pairs; the price was identical in all 31. Price checks were the whole Anthropic
bill in the period (USD 18.17 since 2026-10-01); reservation discovery made no model charge.

## Per booking

| Booking | Pairs | LLM verified | Jev verified | Note |
|---|---|---|---|---|
| Owner, 1 night, USD | 29 | 28 | 28 | Each method failed once, on different runs |
| Invitee A, EUR | 26 | 4 | 25 | LLM mostly `no_equivalent_offer` on an 11-room, 44-rate page |
| Invitee B, EUR, member-discounted room | 27 | 5 | 0 | Jev never priced the booked room's four rates (US-216) |

## Jev failures (29)

- 26 `no_equivalent_offer`: 25 on invitee B (the discounted room), 1 elsewhere.
- 3 `extraction_failed`: Booking.com's error page with nothing to click (US-219). Two are recorded
  by diagnostics; the first has the same signature but predates them.

## LLM-method failures (45)

34 `no_equivalent_offer`, 5 `extraction_failed`, 4 `provider_unavailable`, 2 `timeout`,
1 `budget_exceeded`. One timed-out run left its browser running for nine hours (see maintenance
log); that defect is in the LLM method's teardown and is not fixed here.

## Run order

| First arm | Pairs | Jev verified | LLM verified |
|---|---|---|---|
| LLM method | 43 | 32 | 20 |
| Jev | 39 | 21 | 17 |

Not stratified by booking, so this does not establish an order effect.

## Limits of this evidence

Nine days, three bookings, two users, one model version. Agreement was measured only where both
verified, which excludes invitee B entirely. For invitee A, Jev's 21 extra verifications have no
second method confirming them; the four that do have one agree. The sample cannot establish
general reliability, and no uncertainty interval was computed. The owner chose adoption on
2026-10-06 with these limits stated; a GitHub issue tracks the later review.

## Criterion disposition (US-213)

| Criterion | Disposition |
|---|---|
| Counts with failed arms kept in denominators | Met |
| Arm-only/common/all-in cost split and 1/N inventory allocation | Not applicable in the data (no inventory model charge); allocation logic descoped |
| Percentiles, order/gap, provenance, busy rejects, missed slots, stratification | Partly met (order, per booking, failure classes); remainder descoped |
| Uncertainty for small correlated samples | Stated qualitatively; intervals descoped |
| New cohort on behavior change; report makes no calls and promotes nothing | Met |
