---
id: 002-prove-selected-refund-terms
unit: 001-jev-reservation-facts
intent: 029-jev-reservation-facts
status: draft
priority: must
created: "2026-11-03T19:24:37Z"
assigned_bolt: 097-jev-reservation-facts
implemented: false
---

# US-241: Prove Jev-selected refund terms

## User story

As a BookSaver user, I want refund terms read from wording code does not know, so that refundable stays are monitored and non-refundable ones are not.

## Assigned requirement

FR-1, FR-3, FR-5.

## Acceptance criteria

- [ ] Given the captured Kalipè schedule, when Jev picks the full-refund sentence, then the stay is refundable with deadline 2027-01-23.
- [ ] Given the captured AIRINN Nov 10 wording, when Jev picks it, then the stay is non-refundable.
- [ ] Given a picked sentence without a full-refund or free-cancellation phrase, without a parseable date, or with a date after check-in, when proven, then refund terms stay unknown.

## Out of scope

Partial-refund amounts.
