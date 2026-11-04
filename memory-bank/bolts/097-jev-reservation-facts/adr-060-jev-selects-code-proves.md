---
id: ADR-060
status: accepted
created: 2026-11-03T21:24:43Z
bolt: 097-jev-reservation-facts
amends: ADR-058
---

# ADR-060: Jev reads reservation facts; code wins where it reads them

## Context

The code-owned confirmation reader accepts only exact layouts, so each new Booking.com layout leaves
a booked total or refund terms unknown and the reservation unmonitored. ADR-058 and ADR-059 trust
only code-read facts, because model output must not set money or refund facts.

## Decision

Jev reads the booked total and refund terms on every upcoming confirmation page, asked twice, with
only layout-independent checks (largest amount in its currency in the price area; deadline parsed
from the chosen sentence with a timezone margin). Where the code reader also reads a fact, code wins
and a disagreement is recorded and reported to the owner once a day. Where it cannot, Jev's fact is
used and marked as Jev-read: it may fill a missing total but never replace a saved one, and alerts
based on it say it was read automatically. Only price-area money lines and cancellation sentences
reach TypeSafe; spend counts toward the shared daily cap.

## Consequences

- A new Booking.com layout needs no code change: Jev reads it, and the stall message covers a page
  neither can read.
- A wrong Jev total can cause a missed or a false saving; the alert label tells the user to check.
- Code-read facts keep their exactness, and every page both read measures Jev's accuracy.
- Reservation-page money lines and cancellation sentences reach TypeSafe for every upcoming
  reservation (owner-approved 2026-11-03).

## Alternatives

- New code shapes per layout: always one layout behind.
- Code proofs per layout (the first two versions of this bolt): every safeguard duplicated;
  nine review findings in five rounds.
- Jev always with no comparison: no exactness where code reads, and no drift signal.
