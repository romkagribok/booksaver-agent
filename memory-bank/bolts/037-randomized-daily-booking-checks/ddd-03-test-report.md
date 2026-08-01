---
stage: test
bolt: 037-randomized-daily-booking-checks
created: 2026-08-01T17:39:57Z
---

# Test Report: Randomized Daily Booking Checks

## Summary

- **Full regression**: 1038/1038 tests passed in 10.75 seconds.
- **Focused integrated schedule suite**: 164/164 tests passed across domain generation,
  persistence, dispatch, scheduler, configuration, coordinator, lifecycle, and Telegram status.
- **Static quality**: Ruff passed for `src/` and `tests/`; mypy passed across 100 source files.
- **CLI smoke**: command help loads successfully with the migrated configuration surface.
- **Coverage**: not measured; coverage tooling is not part of the repository quality gate.

## Acceptance Criteria Validation

- **US-119**: default plans contain three UTC slots in distinct eight-hour windows; constrained
  randomness and previous-day boundaries preserve two-hour spacing. SQLite schema v12 makes plans
  idempotent, atomic, recoverable, purge-safe, and bounded by retention.
- **US-120**: the dispatcher orders due work stably, allows only the newest in-grace catch-up, and
  leaves busy slots planned. The coordinator acquires the shared browser gate before claiming and
  then synchronizes and checks exactly the claimed user through existing quotas and safety gates.
- **US-121**: new schedule settings default and validate coherently; legacy `check_interval` remains
  parse-compatible with a deprecation warning and no timing authority. Startup, docs, logs, and
  caller-scoped `/status` expose the randomized model without foreign-user schedule details.

## Migration and Compatibility

- Schema v11 to v12 adds `scheduled_check_slots` and two indexes without rebuilding or deleting
  existing bookings, inventory, checks, traces, savings, sessions, or users.
- Existing fixed-interval config remains readable for migration but is explicitly ignored.
- The daemon retains one process, one adaptive scheduler loop, one coordinator, and one serialized
  Playwright boundary. Manual `/checknow` behavior and human-only Booking.com actions are unchanged.

## Issues Found and Resolved

- The previous lifecycle passed a global interval into the scheduler; it now runs the adaptive
  handler-returned wake loop.
- Existing schema tests pinned version 11; they now validate the complete v8 through v12 migration
  progression.
- Telegram status previously exposed the scheduler's global next wake; it now queries only the
  caller's persisted next slot.

## Review Gate

Implementation and tests are complete. No commit, merge, push, deployment, or live Booking.com or
Telegram smoke test was performed; those remain gated on product-owner review and approval.
