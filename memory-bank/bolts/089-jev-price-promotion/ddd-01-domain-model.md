---
stage: domain-model
bolt: 089-jev-price-promotion
created: "2026-10-10T01:45:20Z"
status: complete
---

# Jev as the price method — domain model

## Value objects and rules

- **PriceExecutorKind** gains `jev` beside `browser_use` and `stagehand`. Exactly one kind is the
  price method of a deployment; there is no automatic fallback between kinds.
- **Authority**: whichever kind is configured produces the canonical result. As authority, Jev may
  keep the independently verified session for refresh; as a comparison candidate it never does.
- **JevPriceRun** (ledger entry): execution id, user, booking, time, executor status, calls,
  tokens, nano-USD cost and certainty, latency, adapter version, content-free diagnostic.
- **DailyJevCap**: spend since 00:00 UTC across authoritative runs and comparison arms must stay
  under `max_daily_cost_usd`; a run is refused, not started, once the cap is reached or the ledger
  cannot be read.
- **Whole-stay total** of a rate card is one of: a line labelled as the price; the amount
  labelled *current price*; a single unlabelled non-nightly amount. It is never a nightly amount,
  an *original* price, a tax/fee/deposit amount, or one of several unlabelled amounts.
- **TotalReason** (diagnostic category): `ok | none | per_night | original | not_total |
  ambiguous | unparsed`.

## Invariants

1. One behavior version names the Jev price method in both roles
   (`JEV_ADAPTER_VERSION == JEV_PRICE_POLICY_VERSION`).
2. `price_executor = jev` and `jev_comparison.enabled` are mutually exclusive.
3. Each price method needs only its own credential; neither key substitutes for the other.
4. Validators, room equivalence, offer selection, savings detection and alert routing are
   unchanged and unaware of which kind produced the observation.
5. Recording a run never changes the check result; failing to record is logged only.

## Ubiquitous language

*Authority / authoritative method*: the configured price method whose result is saved.
*Candidate*: the Jev arm of a paired comparison. *Rollback path*: the LLM price adapters, kept
selectable. *Current price / original price*: the two amounts on a discounted rate card.
