---
bolt: 036-synchronized-booking-interface
stage: design
completed: 2026-07-27T17:02:25Z
---

# Technical Design

- `CheckCoordinator` owns background inventory admission with the same non-overlap lock as checks.
- `/connect` schedules synchronization after encrypted session capture and reports the resulting
  counts; schedule and check-now require a complete refresh before planning or checking.
- `/bookings` acknowledges immediately, refreshes asynchronously, filters the synchronized snapshot
  set to future upcoming stays at the Telegram presentation boundary, and chunks that read-only
  view with human-readable eligibility reasons.
- Telegram registration/edit/delete/rebook handlers and callback routes are not wired or
  published; the CLI exposes no register, occupancy mutation, rebook, rebook-log, or legacy session
  migration command.
- Savings alerts tell the user to act independently in Booking.com and wait for later sync.
