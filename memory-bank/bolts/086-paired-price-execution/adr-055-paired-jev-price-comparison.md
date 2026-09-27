---
adr: ADR-055
status: accepted
created: "2026-09-27T17:00:00Z"
bolt: 086-paired-price-execution
---

# ADR-055: Paired Jev price comparison with baseline-only authority

## Context

The owner wants to compare TypeSafe's Jev with the Browser Use/Anthropic price method on real
checks for several days before deciding on adoption. ADR-043 forbids a second price execution as
a fallback and ADR-048 bounds a combined inventory+price job at 360 s.

## Decision

In explicit paired mode only, run two **independent** child price executions per admitted check —
never as a fallback, never substituting one result for the other. The existing method stays the
sole authority for canonical history, sessions, savings and alerts; the Jev arm is recorded in its
own tables and reported as experimental. The Jev arm has its own ≤ 180 s ceiling, and its actual
run time is added to the job allowance, so the baseline keeps exactly the time it has unpaired. TypeSafe is reached with its own `BOOKSAVER_TYPESAFE_API_KEY`; Jev spend is bounded by a
dedicated daily cap in nano-USD outside the Anthropic ledger. Disabled mode is byte-for-byte the
previous behavior.

## Consequences

Checks take longer and send one extra Telegram message while paired. Booking page text (visible
room/rate card lines and headings, never cookies) is sent to TypeSafe for participating users.
Rollback is `enabled = false` (or removing the key) plus a restart; history is preserved.
