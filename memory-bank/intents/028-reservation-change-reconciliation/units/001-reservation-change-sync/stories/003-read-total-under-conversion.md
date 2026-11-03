---
id: 003-read-total-under-conversion
unit: 001-reservation-change-sync
intent: 028-reservation-change-reconciliation
status: draft
priority: must
created: "2026-11-02T20:51:19Z"
assigned_bolt: 093-reservation-change-sync
implemented: false
---

# US-228: Read the total under a conversion line

## User story

As a BookSaver user, I want my booked total read when the page also shows a converted amount, so that monitoring is not held.

## Assigned requirement

FR-3.

## Acceptance criteria

- [ ] Given the observed rows `1 room € 526`, `12 % TAX € 63`, `approx. € 589` and `US$659.68`, when parsed, then the total is 659.68 USD.
- [ ] Given a conversion in the total's own currency, two conversion lines, one elsewhere, rows in a third currency, no tax row, or rows that miss the conversion by more than 1, when parsed, then the total stays unknown.
- [ ] Given every existing price fixture, when parsed, then the results are unchanged.

## Out of scope

Other layouts.
