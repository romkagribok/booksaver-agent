---
intent: 031-cancelled-card-trip-count
phase: inception
status: context-defined
created: "2026-11-05T23:59:59Z"
updated: "2026-11-05T23:59:59Z"
---

# System Context

## System Overview

`GroupedInventoryReader.run` compares a trip page's status cards with the trip's booking count.

## Context Diagram

```text
trip card (booking_count) -> trip page cards -> count check -> complete or incomplete sync
```

## External Integrations

None.
