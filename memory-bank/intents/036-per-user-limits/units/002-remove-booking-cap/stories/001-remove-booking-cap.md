---
id: 001-remove-booking-cap
unit: 002-remove-booking-cap
intent: 036-per-user-limits
status: complete
priority: must
created: "2026-11-10T01:14:14Z"
assigned_bolt: 108-remove-booking-cap
implemented: true
---

# US-260: Remove the booking cap that was never enforced

## User story

As the owner, I want the configuration to list only limits that are enforced, so that settings mean
what they say.

## Assigned requirement

FR-4.

## Acceptance criteria

- [x] Given no `[limits]` section, when config loads, then `LimitsSettings` has no booking cap.
- [x] Given a config that still sets `max_bookings_per_user` or older retired keys (such as production), when it loads, then it loads and they are ignored.
- [x] Given the retired-keys list and its startup warning, when this ships, then both are gone.

## Out of scope

Adding a real booking limit.
