---
stage: domain-model
bolt: 087-price-comparison-qualification
created: "2026-10-10T01:47:15Z"
status: complete
---

# Comparison evidence — domain model

- **Cohort**: adapter and model version (`jev-price-v1` before 2026-10-01T05:35Z with no runs,
  `jev-price-v2` for all 82 recorded pairs). A behavior change starts a new cohort.
- **Pair**: one admitted price check with a baseline arm and a Jev arm, each `success`, `failure`
  or `not_run`. A failed arm stays in every denominator.
- **Verified**: an arm whose observation passed the unchanged validators and matched the booked
  room. Agreement is defined only where both arms verified.
- **Cost**: method-only model spend per arm (LLM in micro-USD from the Anthropic ledger meter, Jev
  in nano-USD). Reservation discovery made no model charge in the period, so there is no common
  cost to allocate.
