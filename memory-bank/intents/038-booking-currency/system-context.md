---
intent: 038-booking-currency
phase: inception
status: context-defined
created: "2026-11-10T13:26:27Z"
updated: "2026-11-10T13:26:27Z"
---

# System Context

## System Overview

`JevReservationFacts` reads the booked total; it now also asks the booking currency and
`check_total` requires the total to be in it. Reconciliation and price checks are unchanged.

## Context Diagram

```text
confirmation price area -> Jev x2 (total, currency, ...) -> check_total(currency) -> saved total -> price check pins it
```

## External Integrations

TypeSafe (unchanged).
