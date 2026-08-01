---
id: 001-plan-durable-random-daily-slots
unit: 001-randomized-daily-booking-checks
intent: 020-randomized-daily-booking-checks
status: complete
priority: must
created: 2026-08-01T17:14:32.000Z
assigned_bolt: 037-randomized-daily-booking-checks
implemented: true
---

# Story: Plan Durable Random Daily Slots

## User Story

**As a** BookSaver user
**I want** my scheduled booking checks randomized across broad parts of the day
**So that** price changes at different times can be observed without predictable or clustered polling

## Acceptance Criteria

- [ ] **Given** an active user and the default policy, **When** a UTC day is planned, **Then** exactly
  three sorted slots are selected independently inside the day's three eight-hour windows.
- [ ] **Given** adjacent planned slots or a previous-day boundary, **When** times are selected,
  **Then** every pair satisfies the two-hour minimum spacing.
- [ ] **Given** a persisted daily schedule, **When** planning repeats or the daemon restarts, **Then**
  the existing slots are returned without rerolling.
- [ ] **Given** one user/date/ordinal, **When** overlapping work attempts to create or claim it,
  **Then** SQLite uniqueness and atomic transitions prevent duplicate execution.
- [ ] **Given** a process interruption after claim, **When** recovery runs, **Then** indeterminate
  running work becomes missed rather than replayed.
- [ ] **Given** a user purge or expired terminal history, **When** cleanup runs, **Then** executable
  orphan slots cannot remain and retained state stays bounded.

## Technical Notes

- Introduce explicit schedule settings, slot identity/status, planner, and repository contracts.
- Use production system randomness with injected deterministic test seams.
- Persist UTC schedule dates/timestamps in an additive schema migration.

## Dependencies

### Requires

- Existing active-user persistence and SQLite migration infrastructure.

### Enables

- `002-dispatch-due-booking-checks-safely`
- `003-configure-and-observe-randomized-scheduling`

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Previous day ends near midnight | New first slot is redrawn until cross-day spacing is valid |
| Configuration cannot fit within 24 hours | Configuration is rejected before planning |
| Restart while a slot is running | Slot becomes terminal missed, never replayed |
| No active users | No schedule rows are generated |

## Out of Scope

- Per-user timezones, cryptographic secrecy guarantees, or distributed scheduler coordination.
