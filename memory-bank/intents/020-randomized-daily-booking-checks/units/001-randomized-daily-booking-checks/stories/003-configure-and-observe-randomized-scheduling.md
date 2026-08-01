---
id: 003-configure-and-observe-randomized-scheduling
unit: 001-randomized-daily-booking-checks
intent: 020-randomized-daily-booking-checks
status: complete
priority: must
created: 2026-08-01T17:14:32.000Z
assigned_bolt: 037-randomized-daily-booking-checks
implemented: true
---

# Story: Configure and Observe Randomized Scheduling

## User Story

**As a** BookSaver user or self-hosted operator
**I want** validated randomized-schedule settings and caller-scoped next-slot visibility
**So that** I can understand and operate the new cadence without exposing another user's schedule

## Acceptance Criteria

- [ ] **Given** no new schedule keys, **When** config loads, **Then** defaults are three checks per
  eligible booking, two-hour minimum spacing, and one-hour missed-run grace.
- [ ] **Given** invalid or infeasible values, **When** config validates, **Then** startup fails with
  specific field errors before schedule generation.
- [ ] **Given** legacy `check_interval`, **When** config loads, **Then** it remains parse-compatible,
  no longer controls timing, and produces one clear deprecation warning.
- [ ] **Given** a caller uses `/status`, **When** schedule state exists, **Then** only that caller's
  next planned slot or clear none reason is shown.
- [ ] **Given** schedule planning and dispatch, **When** operators inspect logs, **Then** redacted slot
  identity, time, lateness, and lifecycle outcomes are visible without booking/session secrets.
- [ ] **Given** generated config, README, CLI output, or VPS instructions, **When** users follow them,
  **Then** they see daily randomized scheduling rather than fixed-interval guidance.
- [ ] **Given** the daemon starts, stops, or encounters an idle schedule, **When** watchdog and
  lifecycle checks run, **Then** health and prompt shutdown remain compatible.

## Technical Notes

- Introduce a `ScheduleSettings` projection in `Config`; keep legacy parsing isolated to the loader.
- Query next slot by stable local user identity at the Telegram presentation boundary.
- Update example config, config show/validate, startup output, README, and VPS runbook.

## Dependencies

### Requires

- `001-plan-durable-random-daily-slots`
- `002-dispatch-due-booking-checks-safely`

### Enables

- Operational verification and future schedule tuning.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Caller has no planned future slot yet | `/status` gives a non-error pending/unavailable explanation |
| Config changes after today's slots exist | Persisted slots remain stable; future days use new settings |
| Operator lowers quota below bookings × slots | Quota remains authoritative and capped outcomes stay visible |
| Owner asks aggregate status | Counts may be shown without foreign-user detailed times |

## Out of Scope

- User-facing timezone settings, schedule-editing commands, or deployment automation.
