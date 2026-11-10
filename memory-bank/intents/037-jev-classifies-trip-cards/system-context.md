---
intent: 037-jev-classifies-trip-cards
phase: inception
status: context-defined
created: "2026-11-10T02:08:13Z"
updated: "2026-11-10T02:08:13Z"
---

# System Context

## System Overview

`GroupedInventoryReader` visits each trip page; it now asks `JevReservationFacts.classify_cards`
for the trip's cards and uses the classes for the count check, the targets to open, completed-stay
skips and cancellation claims, falling back to the code status words when Jev has no answer.

## Context Diagram

```text
trip page -> cards (merged per booking, personal lines removed) -> Jev x2 -> classes -> count check / open / skip
```

## External Integrations

TypeSafe (unchanged).
