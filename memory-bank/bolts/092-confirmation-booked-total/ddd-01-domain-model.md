---
unit: 013-confirmation-booked-total
bolt: 092-confirmation-booked-total
stage: model
status: complete
created: 2026-10-10T02:00:18Z
updated: 2026-10-10T02:00:18Z
---

# Static Model - Confirmation Booked Total

## Bounded Context

Account inventory reading and reconciliation for one caller. The confirmation page is the
caller's own statement of what was booked; price monitoring consumes the result but is outside
this context.

## Domain Entities

- **Reservation**: caller-owned confirmation identity with saved stay, room, occupancy,
  refundability and booked total. Its booked total is authoritative once saved and changes only
  under the replacement rule below.
- **Monitoring booking**: projection of an eligible reservation. Its baseline price always equals
  the reservation's booked total, in the same currency; it never holds a converted amount.
- **Confirmation reading**: one code-owned reading of one rendered confirmation page in the
  current run. It either reconciles a booked total or leaves it unknown with a reason.

## Value Objects

- **Printed money**: a currency and an amount exactly as the page prints them. The currency comes
  from a recognized symbol or ISO code placed before the amount; the amount uses en-US grouping.
  An unrecognized token or grouping is not money.
- **Booked total**: the all-in printed money the guest owes for the stay. It is reconciled only
  when the room row plus each recognized tax or city-tax row equals the stated total and every
  one of those amounts shares the total's currency.
- **Total provenance**: page-verified (reconciled by the code-owned confirmation reading) or
  unverified (anything a provider submitted, or any merge that includes provider output).
- **Refund window**: free until one local moment and charged or non-refundable from the adjacent
  moment. It is stated either by two cost tiers in one currency or by one refund schedule
  sentence; cost tiers, when rendered at all, are the only source considered.
- **Unknown-fact reason**: a fixed code naming the rule that stopped a total or refund window from
  being established. It carries no page text, amount, name or identifier.

## Aggregates

- **Reservation** is the aggregate root; its monitoring booking and its stale savings
  opportunities change with it in one transaction.
- Invariants: one booked total in one currency; a monitoring baseline never differs from the
  reservation's booked total; a saved total is never replaced by an unverified total; a changed
  baseline leaves no savings opportunity computed against the old one; other callers' rows are
  never touched.

## Domain Events

- **BookedTotalReconciled**: a confirmation reading established a page-verified total.
- **BookedTotalReplaced**: a page-verified total differed from the saved one and replaced it,
  together with the monitoring baseline; stale opportunities were removed.
- **BookedTotalUnknown**: a confirmation was read but no total was established; the reason code is
  counted. Saved facts are unchanged.
- **UnverifiedTotalConflict**: an unverified total differed from the saved one; the refresh fails
  closed and nothing is changed.

## Domain Services

- **Confirmation fact reading**: turns rendered confirmation text into printed money, booked total,
  refund window and reasons. It has no browser or persistence access and never converts.
- **Reservation reconciliation**: applies a reading to the saved reservation under the saved-fact
  conflict rules, with the single replacement exception for a page-verified total.

## Repository Interfaces

- **Account reservation repository**: unchanged contract. Reconcile validated observations for one
  caller and run atomically; any conflict rolls back the whole reconciliation.

## Ubiquitous Language

- **Booked total / baseline**: the price the guest pays for the existing reservation; what a live
  offer must beat.
- **Printed currency**: the currency shown on the confirmation page, never the account's display
  preference and never a converted figure.
- **Page-verified**: established by BookSaver's own reading of the confirmation page, not by a
  model or provider.
- **Stale baseline**: a saved booked total that differs from the page-verified one.

## Story coverage

US-226: printed money, booked total, refund window. US-227: total provenance, replacement
invariants and events. US-228: unknown-fact reason and the affected-caller acceptance boundary.
