---
id: 001-jev-reads-room-type
unit: 001-jev-reads-room-type
intent: 033-jev-reads-room-type
status: complete
priority: must
created: "2026-11-08T02:21:32Z"
assigned_bolt: 104-jev-reads-room-type
implemented: true
---

# US-256: Jev reads the room type and agreed totals count

## User story

As a BookSaver user with a new reservation, I want its room, total and meals read whatever the page
layout, so that price checks start without anyone changing code.

## Assigned requirement

FR-1 to FR-5.

## Acceptance criteria

- [x] Given both Jev calls choose the same room line, when synced, then that line is the room type.
- [x] Given they disagree or are below 0.5, when synced, then the room type stays unknown.
- [x] Given both calls choose the same code-checked total at low confidence, when synced, then the total is read.
- [x] Given a single-room party with a meal row and an unrecognised room layout, when synced, then the meal plan is read.
- [x] Given prices found but none for the booked room, when checked, then the detail says "No matching room type found".
- [x] Given Park Plaza's real page on staging, when synced, then it is eligible and other reservations keep their room types.

## Out of scope

Room equivalence in price checks.
