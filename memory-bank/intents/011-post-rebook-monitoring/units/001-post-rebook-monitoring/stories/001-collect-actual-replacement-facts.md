---
id: 001-collect-actual-replacement-facts
unit: 001-post-rebook-monitoring
intent: 011-post-rebook-monitoring
status: complete
priority: must
created: 2026-07-19T19:50:29.000Z
assigned_bolt: 023-post-rebook-monitoring
implemented: true
---

# Story: Collect Actual Replacement Facts

**Global story ID**: US-072

## User Story

**As a** user who completed the replacement booking on my device
**I want** to give BookSaver the actual confirmation, Booking.com URL, and total paid
**So that** monitoring does not mistake a detected offer for my final reservation

## Acceptance Criteria

- [ ] Replacement facts are requested only after reported booking completion.
- [ ] Confirmation, same-property Booking.com URL, and actual Money are validated.
- [ ] Every accepted answer is acknowledged and a final summary requires explicit confirmation.
- [ ] The detected offer price is never used as the replacement baseline.

## Dependencies

- US-033 device handoff outcome follow-up.
