---
id: ADR-065
status: accepted
created: 2026-11-10T01:15:25Z
bolt: 109-same-or-better-room
amends: ADR-064
---

# ADR-065: A cheaper same-or-better room is a saving

## Context

ADR-064 compared only the room Jev named as the booked room type. On AIRINN's page for 2026-11-17
that room is no longer sold; only a balcony version, Business and Comfort rooms are. The owner decided
a cheaper offer for the same or a better room is a saving worth reporting.

## Decision

Jev compares every priced room that does not carry the booked name with the booked room, for the
booked guests: same, better, or neither (worse, different bed setup, unclear). Both of two runs must
agree at 0.8. Same and better rooms are compared on price; the alert names the offered room and says
whether it is better.

## Consequences

- Savings appear even when the exact room type is sold out.
- "Better" is Jev's judgement; the alert shows the room so the guest decides.
- Different bed setups (twin for double) are never better.

## Alternatives

Same room only (ADR-064): misses real savings when the booked room is sold out.
