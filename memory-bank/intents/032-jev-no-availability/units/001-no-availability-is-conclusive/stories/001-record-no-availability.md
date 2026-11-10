---
id: 001-record-no-availability
unit: 001-no-availability-is-conclusive
intent: 032-jev-no-availability
status: complete
priority: must
created: "2026-11-06T16:53:03Z"
assigned_bolt: 103-no-availability-is-conclusive
implemented: true
---

# US-255: Record "no availability for your dates" as conclusive

## User story

As a BookSaver user whose hotel has nothing left for my dates, I want that recorded as a normal
result, so that my reservation does not look broken or trigger a stall message.

## Assigned requirement

FR-1 to FR-3.

## Acceptance criteria

- [x] Given a page listing only other dates and a confident Jev answer, when checked, then the result is no equivalent offer.
- [x] Given an unsure or "rooms listed" answer, when checked, then the result is unchanged (no valid observation).
- [x] Given a page where rooms are named, when checked, then no availability question is asked.
- [x] Given Kalipè's real page on staging, when checked, then the result is no equivalent offer.

## Out of scope

Rooms that are listed but not equivalent.
