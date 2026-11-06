---
id: 002-remove-code-price-and-refund-parsing
unit: 001-jev-reservation-reader
intent: 030-jev-only-booksaver
status: complete
priority: must
created: "2026-11-04T15:34:52Z"
assigned_bolt: 098-jev-reservation-reader
implemented: true
---

# US-244: Remove the code price and refund parsing

## User story

As the owner, I want no layout-specific price or refund code, so that nothing needs updating when Booking.com changes.

## Assigned requirement

FR-1, FR-5.

## Acceptance criteria

- [ ] Given the confirmation parser, when read, then it has no price or cancellation section parsing.
- [ ] Given the sync, when Jev and a saved fact differ, then no comparison or owner notice runs.
- [ ] Given a savings alert, when rendered, then it has no "read automatically" line.

## Out of scope

The Claude removal.
