---
id: ADR-064
status: accepted
created: 2026-11-10T00:36:30Z
bolt: 106-jev-judges-room-and-rate-terms
---

# ADR-064: Jev judges room equivalence and rate terms; code keeps identity and totals

## Context

Exact room-name equality left two production bookings unpriced for days when the hotel page named
the room differently from the confirmation. English patterns vetoed Jev's meal, refund and tax answers,
and an exact hotel-name comparison duplicated the Booking.com link proof. Each needs code changes
whenever wording changes; the owner wants near-zero maintenance.

## Decision

Jev chooses which priced room is the booked one (all page rooms shown, asked twice, agreement at 0.8),
classifies each rate's meals, and its refund and tax answers count when it names the stating line at
0.8. A matching Booking.com link proves the hotel. Code keeps the whole-stay total grounding, stay and
party identity, and offer selection.

## Consequences

- Room renames, meal, refund and tax rewordings need no code change.
- A Jev misjudgement is bounded by the named-line, confidence and two-run rules; an unsure answer only
  excludes offers.
- Total grounding still uses Booking.com's labels; if they change, checks fail loudly.

## Alternatives

Fuzzy room-name matching in code: still a rule set to maintain and blind to the other rooms on the page.
