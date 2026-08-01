---
id: 002-dispatch-due-booking-checks-safely
unit: 001-randomized-daily-booking-checks
intent: 020-randomized-daily-booking-checks
status: complete
priority: must
created: 2026-08-01T17:14:32.000Z
assigned_bolt: 037-randomized-daily-booking-checks
implemented: true
---

# Story: Dispatch Due Booking Checks Safely

## User Story

**As a** BookSaver user with eligible synchronized bookings
**I want** every booking checked once at each of my three due daily slots
**So that** randomized scheduling improves coverage without weakening fairness or browser safety

## Acceptance Criteria

- [ ] **Given** a claimable due slot, **When** it is dispatched, **Then** BookSaver synchronizes that
  user once and runs the ordinary pipeline for every currently eligible booking.
- [ ] **Given** a continuously eligible booking and an available complete day, **When** all slots
  execute, **Then** the booking receives exactly three scheduled attempts.
- [ ] **Given** simultaneous due users, **When** dispatch orders them, **Then** planned time and a
  stable tie-breaker preserve fairness through the one coordinator/browser gate.
- [ ] **Given** `/checknow` or other browser work owns the gate, **When** a slot is still inside its
  one-hour grace, **Then** it remains retryable and is not falsely completed.
- [ ] **Given** overdue slots or a restart, **When** recovery runs, **Then** at most the newest slot
  inside grace can catch up and older work becomes missed without a burst.
- [ ] **Given** a previous scheduled batch started less than two hours ago, **When** another slot is
  due, **Then** actual execution waits within grace or becomes missed.
- [ ] **Given** quota exhaustion, revocation, synchronization failure, or changed eligibility,
  **When** execution reaches that boundary, **Then** existing fail-closed semantics remain
  authoritative.

## Technical Notes

- Extend the coordinator with user-scoped scheduled batches rather than adding another monitor path.
- Atomically claim only after verifying due/grace/spacing; record terminal lifecycle separately from
  individual booking-check history.
- Keep manual checks independent from scheduled slot satisfaction.

## Dependencies

### Requires

- `001-plan-durable-random-daily-slots`
- Existing synchronized inventory and `CheckCoordinator`.

### Enables

- `003-configure-and-observe-randomized-scheduling`

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User has no eligible bookings after synchronization | Slot completes without fabricated booking failures |
| User is revoked after due selection | Slot cannot open owner-scoped browser work |
| Several users share the same planned minute | Users serialize in stable order; no overlapping browsers |
| Check duration crosses into the next user's slot | Lateness is recorded and the later slot respects grace |

## Out of Scope

- Parallel Playwright, queued manual checks, or changing the booking/LLM daily quota model.
