---
intent: 036-per-user-limits
phase: inception
status: context-defined
created: "2026-11-10T00:46:00Z"
updated: "2026-11-10T00:46:00Z"
---

# System Context

## System Overview

`JevPrimaryPriceExecutor` (price checks) and `remaining_daily_nano_usd` (sync reservation facts) read
today's Jev spend from `jev_price_runs` and `price_comparison_arms` and refuse or shrink the run
budget against `jev_comparison.max_daily_cost_usd`. Both rows already carry `user_id`.

## Context Diagram

```text
request (owner_user_id) -> today's Jev spend for that user -> cap - spend -> Jev run budget (0 = refused)
```

## External Integrations

TypeSafe (unchanged).
