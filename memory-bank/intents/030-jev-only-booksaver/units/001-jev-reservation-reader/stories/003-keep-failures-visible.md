---
id: 003-keep-failures-visible
unit: 001-jev-reservation-reader
intent: 030-jev-only-booksaver
status: draft
priority: must
created: "2026-11-04T15:34:52Z"
assigned_bolt: 098-jev-reservation-reader
implemented: false
---

# US-245: Keep failures visible without notices

## User story

As a BookSaver user, I want an unreadable reservation reported, so that nothing is silently unmonitored.

## Assigned requirement

FR-6.

## Acceptance criteria

- [ ] Given Jev unavailable, when synced, then saved totals and refund terms are kept.
- [ ] Given a new reservation Jev cannot read for 24 hours, when a scheduled run ends, then its user gets the stall message.

## Out of scope

New notices.
