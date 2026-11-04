---
id: 001-read-with-jev-alone
unit: 001-jev-reservation-reader
intent: 030-jev-only-booksaver
status: draft
priority: must
created: "2026-11-04T15:34:52Z"
assigned_bolt: 098-jev-reservation-reader
implemented: false
---

# US-243: Read totals and refund terms with Jev alone

## User story

As a BookSaver user, I want my booked total and refund terms read on any layout, so that monitoring needs no maintenance.

## Assigned requirement

FR-1 to FR-4.

## Acceptance criteria

- [ ] Given the owner's and dad's pages on staging, when synced, then all seven reservations get the right total and refund terms.
- [ ] Given a dated cancellation-cost line, when Jev picks it, then the deadline is that exact date.
- [ ] Given "within N months", when parsed, then calendar months are used.
- [ ] Given an agreed Jev total that differs from the saved one, when synced, then it replaces it.
- [ ] Given answers that disagree or fall below the confidence bars, when synced, then that fact stays as saved.

## Out of scope

Other confirmation facts.
