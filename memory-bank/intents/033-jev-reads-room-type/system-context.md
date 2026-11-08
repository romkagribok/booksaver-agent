---
intent: 033-jev-reads-room-type
phase: inception
status: context-defined
created: "2026-11-08T02:21:32Z"
updated: "2026-11-08T02:21:32Z"
---

# System Context

## System Overview

`JevReservationFacts` (sync assist on upcoming confirmation pages) gains a room question;
`parse_confirmation_facts` no longer parses the room; the monitor's room-mismatch detail is reworded.

## Context Diagram

```text
confirmation page -> code facts (dates, party, meals) -> Jev (total, refund, room) -> account reservation
```

## External Integrations

TypeSafe (unchanged).
