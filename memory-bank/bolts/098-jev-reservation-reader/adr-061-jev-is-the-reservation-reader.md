---
id: ADR-061
status: accepted
created: 2026-11-04T15:35:28Z
bolt: 098-jev-reservation-reader
supersedes: ADR-060
---

# ADR-061: Jev is the only reader of booked totals and refund terms

## Context

ADR-060 kept the code reader first and compared it with Jev. The comparison produced a false
disagreement on its first day (its own date arithmetic), and the code reader is the part that needs
changes whenever Booking.com changes a page. The owner wants near-zero maintenance and judged Jev
trustworthy enough to rely on alone.

## Decision

Jev reads the booked total and refund terms on every upcoming confirmation, asked twice, with only
layout-independent checks. Its agreed, checked total is page-verified and may replace a saved one.
The code reader stops parsing price and cancellation sections; the comparison, owner notice and
alert label are removed.

## Consequences

- No layout-specific price or refund code to maintain.
- No cross-check: a Jev misread is caught only by the largest-amount and two-run rules.
- A Jev outage keeps saved facts; new or changed reservations wait, and the stall message covers them.

## Alternatives

ADR-060 (code first, compare): kept exactness and a drift signal, at the cost of two readers.
