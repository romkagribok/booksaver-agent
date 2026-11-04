---
id: 001-prove-selected-total
unit: 001-jev-reservation-facts
intent: 029-jev-reservation-facts
status: draft
priority: must
created: "2026-11-03T19:24:37Z"
assigned_bolt: 097-jev-reservation-facts
implemented: false
---

# US-240: Prove a Jev-selected booked total

## User story

As a BookSaver user, I want my booked total read on layouts code does not know, so that my reservation is monitored.

## Assigned requirement

FR-1, FR-2, FR-4, FR-5.

## Acceptance criteria

- [ ] Given a total the code reader read, when syncing, then Jev is not asked.
- [ ] Given the captured Hampton, Best Western and AIRINN Nov 17 sections, when Jev picks the total, then 577.42 USD, 521.11 USD and 102 EUR are stored as page-verified.
- [ ] Given a pick the rows do not sum to, a nightly amount, a second amount in the same currency, or a line outside the price section, when proven, then the total stays unknown.
- [ ] Given the question sent to TypeSafe, when inspected, then it contains only candidate lines, with no name, address or confirmation number.
- [ ] Given Jev unavailable or erroring, when syncing, then the result is as today.

## Out of scope

Stay dates, room and occupancy.
