---
id: 001-synchronize-every-freshness-boundary
unit: 002-synchronized-booking-interface
intent: 019-booking-account-synchronization
status: complete
priority: must
created: 2026-07-27T16:28:04.000Z
assigned_bolt: 036-synchronized-booking-interface
implemented: true
---

# Story: US-116 Synchronize at every freshness boundary

## User Story

**As a** BookSaver user
**I want** every view or check to use current Booking.com reservation state
**So that** monitoring never relies on manually maintained facts.

## Acceptance Criteria

- [ ] Successful `/connect` and supported session intake trigger caller synchronization.
- [ ] Scheduled work synchronizes each user once before planning that user's eligible checks.
- [ ] `/checknow` synchronizes before resolving/checking the selected reservation.
- [ ] `/bookings` synchronizes before rendering inventory.
- [ ] Accepted asynchronous Telegram work is acknowledged within two seconds under normal conditions.
- [ ] Failed/incomplete prerequisite synchronization prevents affected price checks and gives
  caller-scoped recovery guidance.

## Dependencies

### Requires
- Unit 001 complete.

### Enables
- US-117.

## Out of Scope

- New browser concurrency or queued work model.
