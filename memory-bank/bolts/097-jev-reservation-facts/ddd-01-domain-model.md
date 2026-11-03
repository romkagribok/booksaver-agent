---
unit: 001-jev-reservation-facts
bolt: 097-jev-reservation-facts
stage: model
status: complete
created: 2026-11-03T21:24:43Z
updated: 2026-11-03T21:24:43Z
---

# Static Model - Jev-assisted Reservation Facts

## Bounded Context

Reading one confirmation page during account sync. Reconciliation (ADR-058, ADR-059) consumes the
result unchanged.

## Domain Entities

- **Confirmation reading**: the code reader's facts plus reason codes for unknown facts.
- **Assisted reading**: one Jev question set about the unknown facts of one page.

## Value Objects

- **Candidate line**: a line of the page that code selected as a possible answer. Only these and the
  question leave the server.
- **Pick**: Jev's choice of one candidate, or none.
- **Proof**: the code check that turns a pick into a fact.
  - Total: room and tax rows sum to the pick in its currency, or to the `approx.` line directly above
    it in another currency (display rounding of 1 there only); at least one tax row, each matching
    its room row; the pick is the only amount in its currency in the price section; no charge
    warning.
  - Refundable: the picked sentence has a full-refund or free-cancellation phrase and exactly one
    date, on or before check-in and not before today; that date is the deadline.
  - Non-refundable: the picked sentence says so explicitly and has no full-refund phrase.

## Domain Rules

1. Code facts stand; Jev is asked only about unknown total or refund terms.
2. A proven fact is page-verified; an unproven pick changes nothing.
3. Spend counts toward the Jev daily cap; over it, nothing is asked.
4. Unreadable upcoming stays count as stalled after 24 hours (extends bolt 095).
