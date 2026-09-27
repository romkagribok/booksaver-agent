---
stage: domain-model
bolt: 085-jev-price-executor
created: "2026-09-27T17:00:00Z"
status: complete
---

# Jev price executor — domain model

- `JevComparisonSettings` (`domain/price_comparison.py`): disabled by default; pinned model
  `jev-1.13.0` only; participants `owner|all`; per-arm call cap ≤ 120; arm timeout 30–180 s;
  daily Jev cap ≤ USD 1.00.
- `JevUsage`: calls, input/output tokens, **nano-USD** cost, certainty (exact/conservative).
  Price: 42 nano-USD per input token (USD 0.042 / 1M), output free. Per-call spend is mirrored into
  the provider-neutral `ExecutionMeter` rounded **up** to microdollars.
- `ObservationSource.JEV_PRICE_SUBMISSION` marks provenance; the result contract
  (`PriceExecutionResult`) and validators are unchanged.
- Invariants: no refreshed session from the candidate; no non-Jev inference; every attempt that
  may have been billed without usage (timeouts, 5xx, unusable 200) is charged conservatively from
  a request-size estimate; a model-version mismatch fails closed after charging its usage.
