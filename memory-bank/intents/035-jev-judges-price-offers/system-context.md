---
intent: 035-jev-judges-price-offers
phase: inception
status: context-defined
created: "2026-11-10T00:36:30Z"
updated: "2026-11-10T00:36:30Z"
---

# System Context

## System Overview

`JevPriceExecutor` names rooms and asks per-rate questions; it now also asks the room question (FR-1)
and per-rate meal, refund-line and tax-line questions. `query_identity_rejection` accepts a proven
hotel link without exact name equality. The monitor matches rooms by name or by Jev's judgement.

## Context Diagram

```text
hotel page -> Jev (property, room names, rate terms, booked room x2) -> code (total grounding, identity) -> offer selection
```

## External Integrations

TypeSafe (unchanged).
