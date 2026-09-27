---
stage: domain-model
bolt: 086-paired-price-execution
created: "2026-09-27T17:00:00Z"
status: complete
---

# Paired price execution — domain model

- `PriceComparison`: id, user, booking, trigger (`check_now|scheduled`), cohort
  (`jev-price-v1:jev-1.13.0`), persisted random `first_arm`, report status
  (`pending|sent|failed|suppressed`).
- `ArmResult` per arm (`baseline|jev`): `success|failure|not_run`, outcome code, validated
  live price, savings versus the booked price (display only), calls/tokens, nano-USD cost and
  certainty, start/finish. A failure or not-run never carries a price and is never "no savings".
- Authority: only the baseline arm writes check history/traces, session refresh, failure
  counters, canary metrics, savings rows and alerts. The Jev arm writes only its comparison row.
