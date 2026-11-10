---
id: 001-jev-reads-party-meals-dates
unit: 001-jev-reads-party-meals-dates
intent: 034-jev-reads-reservation-facts
status: complete
priority: must
created: "2026-11-08T18:31:21Z"
assigned_bolt: 105-jev-reads-party-meals-dates
implemented: true
---

# US-257: Jev reads the booked party, meals and missing dates

## User story

As a BookSaver user, I want my reservation's guests and meals read correctly whatever the wording, so
that bookings with children are checked and I never get a savings alert for a worse meal plan.

## Assigned requirement

FR-1 to FR-6.

## Acceptance criteria

- [x] Given agreed adults, children, rooms and nights matching the dates, when synced, then the party is recorded.
- [x] Given disagreement or nights not matching, when synced, then the party stays unknown.
- [x] Given an agreed meal class, when synced, then it is recorded with its line; "not stated" stays unknown.
- [x] Given dates code cannot read, when synced, then Jev's agreed dates are used and the lifecycle follows them.
- [x] Given a hotel link with a query, when synced, then the property is kept without the query.
- [x] Given a page with guest name, email, phone, confirmation number and PIN, when asked, then none reaches TypeSafe.
- [x] Given the real pages on staging, when synced, then every reservation keeps its party, meals and eligibility.

## Out of scope

Price checks and discovery.
