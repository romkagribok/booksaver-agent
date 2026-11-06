---
intent: 032-jev-no-availability
phase: inception
status: context-defined
created: "2026-11-06T16:53:03Z"
updated: "2026-11-06T16:53:03Z"
---

# System Context

## System Overview

`LocalJevPriceRuntime._extract` names rooms with Jev; when none is named it now asks one availability
question; `PriceExecutionStatus.UNAVAILABLE` already maps to `no_equivalent_offer`.

## Context Diagram

```text
property page -> Jev room names (none) -> Jev availability question -> unavailable -> no_equivalent_offer
```

## External Integrations

TypeSafe (unchanged).
