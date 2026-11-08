---
intent: 034-jev-reads-reservation-facts
phase: inception
status: context-defined
created: "2026-11-08T18:31:21Z"
updated: "2026-11-08T18:31:21Z"
---

# System Context

## System Overview

`parse_confirmation_facts` keeps identity, dates and the hotel link; `JevReservationFacts` reads total,
refund, room, party, meals and missing dates; the grouped reader asks Jev for upcoming pages and pages
whose dates code could not read.

## Context Diagram

```text
confirmation page -> code (confirmation, dates, hotel link) -> Jev x2 (total, refund, room, party, meals, dates?) -> code checks -> account reservation
```

## External Integrations

TypeSafe (unchanged).
