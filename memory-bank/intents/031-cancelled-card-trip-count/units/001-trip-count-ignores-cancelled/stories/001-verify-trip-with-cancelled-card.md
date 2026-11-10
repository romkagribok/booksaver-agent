---
id: 001-verify-trip-with-cancelled-card
unit: 001-trip-count-ignores-cancelled
intent: 031-cancelled-card-trip-count
status: complete
priority: must
created: "2026-11-05T23:59:59Z"
assigned_bolt: 102-trip-count-ignores-cancelled
implemented: true
---

# US-254: Verify a trip that contains a cancelled card

## User story

As a BookSaver user who cancels or rebooks, I want my account read completely, so that superseded
reservations are retired and nothing misleading is sent.

## Assigned requirement

FR-1, FR-2.

## Acceptance criteria

- [x] Given four confirmed hotel cards, one canceled card and one car rental with a count of five, when read, then the trip is verified and the sync is complete.
- [x] Given the same trip, when read, then the canceled card is still opened and recorded.
- [x] Given a count that matches neither way, when read, then the trip stays unverified.
- [x] Given the dad's account on staging, when synced, then the sync is complete and the superseded Best Western is no longer upcoming.

## Out of scope

Other incomplete-sync causes.
