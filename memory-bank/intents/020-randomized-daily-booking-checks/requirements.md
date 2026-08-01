---
intent: 020-randomized-daily-booking-checks
phase: inception
status: complete
created: 2026-08-01T17:03:32.000Z
updated: 2026-08-01T17:17:15.000Z
---

# Requirements: Randomized Daily Booking Checks

## Intent Overview

Replace BookSaver's one fixed global check interval with restart-safe, broadly distributed daily
check slots for each active user. By default, every eligible booking is checked three times during a
full UTC day: once at a random time in each broad third of the day, with scheduled executions never
closer than two hours.

The schedule remains self-hosted and uses the existing single coordinator, authenticated account
synchronization, per-user limits, and serialized browser boundary. Randomization changes only when
scheduled checks are admitted; it does not weaken booking equivalence, price-source, privacy, or
human-action requirements.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Observe price changes across different parts of the day | Every continuously eligible booking receives one scheduled check in each of three broad UTC windows when the daemon is available | Must |
| Avoid synchronized and predictable polling | Exact slot times differ by user and UTC date and are selected randomly within their windows | Must |
| Prevent clustered scheduled work | Planned and actual scheduled batches for one user are separated by at least two hours | Must |
| Survive normal VPS restarts safely | Persisted slots are neither rerolled nor executed more than once after restart | Must |
| Preserve current safety and cost controls | All scheduled work continues through the existing coordinator, session, quota, and browser boundaries | Must |

## Approved Product Direction

- Schedule three user-level slots per UTC day by default; every booking that is active and eligible
  at a slot receives one ordinary price check in that slot's user batch.
- Divide each UTC day into three equal eight-hour windows and randomly select one exact time within
  each window for each user and date.
- Enforce a two-hour minimum between planned slots and between actual scheduled batch starts,
  including the previous day's final slot and the next day's first slot.
- Persist planned slots and their lifecycle in SQLite so a daemon restart cannot reroll or duplicate
  work.
- Permit at most one catch-up when a slot is no more than one hour overdue; older slots are recorded
  as missed and are never replayed in a burst.
- Use UTC for the schedule and day boundary. Per-user local timezones are a separate future feature.
- Keep Telegram `/checknow` independent. Manual checks share the browser gate and daily booking-check
  quota but do not replace or move scheduled slots.

## Scope

### In Scope

- Random, broadly distributed daily slot generation per active user.
- Durable slot planning, claiming, completion, and missed-state recording.
- Scheduled dispatch of only users whose slots are due.
- One account synchronization per due user before checking all currently eligible bookings.
- Restart, downtime, busy-coordinator, revocation, and UTC-day rollover behavior.
- Schedule configuration, validation, legacy `check_interval` migration, logs, and `/status` output.
- Focused, property-based, integration, lifecycle, and regression tests.

### Out of Scope

- Per-user timezone preferences or daylight-saving-time behavior.
- Concurrent Playwright browsers, distributed workers, cron, APScheduler, or another scheduler.
- Guaranteeing three completed checks when the daemon, Booking.com, or the user's authenticated
  session is unavailable.
- Replacing manual `/checknow`, changing daily cost caps, or persisting existing in-memory quota
  counters.
- Autonomous reservation, cancellation, payment, purchase, or final booking actions.

## Functional Requirements

### FR-1: Generate random, broadly distributed daily slots

- **Description**: BookSaver must create a durable daily schedule for each active user using one
  random slot in each equal segment of the UTC day.
- **Acceptance Criteria**:
  - The default schedule contains exactly three sorted, timezone-aware UTC slots per user and date.
  - The three default selection windows are `[00:00, 08:00)`, `[08:00, 16:00)`, and
    `[16:00, 24:00)` UTC.
  - The exact instant in each window is selected with a production random source and is not derived
    from daemon startup time or a shared global offset.
  - Slot generation is independent per user and UTC date; users are not intentionally aligned to
    the same three instants.
  - Every adjacent pair is at least the configured minimum spacing apart, including the prior
    date's final persisted slot and the new date's first slot.
  - Once persisted, a user's slots for a date never change because of a restart, config reload, or
    repeated planning call.
  - Random-source and clock dependencies are injectable so tests are deterministic without making
    production schedules deterministic.
- **Priority**: Must
- **Related Stories**: US-119

### FR-2: Check every eligible booking at each due user slot

- **Description**: A due slot represents one scheduled batch for one user. The batch synchronizes
  that user's Booking.com account once, then runs the ordinary monitoring pipeline for every booking
  that is active and eligible in the conclusive synchronized inventory.
- **Acceptance Criteria**:
  - A booking that remains eligible for a complete UTC day receives three scheduled price-check
    attempts when all three slots are admitted and the daemon remains available.
  - A booking discovered, reactivated, or made eligible during the day participates only in the
    user's remaining slots; BookSaver does not create compressed replacement slots.
  - A booking made inactive, ineligible, absent, past, or cancelled before execution is not checked.
  - Account inventory synchronization runs once per due user slot, not once per booking.
  - A conclusive synchronization result supplies the booking set and facts for that slot; failed or
    incomplete synchronization fails closed under the existing account-synchronization rules.
  - Each admitted booking check consumes one existing `max_checks_per_user_per_day` allowance. A
    three-booking user can therefore consume up to nine scheduled booking-check allowances per day.
  - Within a due-user group, booking work retains existing round-robin planning, fresh browser
    contexts, revocation checks, history, trace, savings, and notification behavior.
- **Priority**: Must
- **Related Stories**: US-120

### FR-3: Persist schedule lifecycle and suppress duplicate execution

- **Description**: BookSaver must persist enough per-user slot state to make scheduling observable
  and safe across process restarts.
- **Acceptance Criteria**:
  - SQLite stores the user, UTC schedule date, slot ordinal, planned time, lifecycle status, and
    relevant attempt/completion timestamps for each slot.
  - The slot identity is unique for one user, date, and ordinal.
  - Claiming a planned slot is atomic so one slot cannot be admitted twice by overlapping dispatcher
    iterations.
  - A completed or missed slot is never executed later.
  - A slot left in an indeterminate running state by process termination is recovered conservatively
    as missed rather than replayed and risking duplicate browser work.
  - Revoked or deleted users cannot retain executable slots; deletion follows existing user purge
    and foreign-key boundaries.
  - Old terminal schedule rows are pruned with a bounded retention policy without removing current
    or future plans.
- **Priority**: Must
- **Related Stories**: US-119

### FR-4: Dispatch due users through the existing coordinator

- **Description**: The scheduler must wake interruptibly, identify due user slots, and route them
  through the one existing `CheckCoordinator` and browser gate without creating a parallel
  monitoring path.
- **Acceptance Criteria**:
  - The scheduler does not run a global all-user batch at daemon startup.
  - Only users with due, claimable slots are offered to scheduled execution.
  - Simultaneously due users are processed in planned-time order with a stable fairness tie-breaker.
  - The coordinator continues to allow at most one scheduled or manual browser batch in the process.
  - A user's slot is not marked completed merely because the coordinator was busy.
  - Revocation and booking ownership are rechecked immediately before allowance reservation and
    browser work.
  - The scheduler wait remains based on `threading.Event` and wakes immediately on shutdown.
  - No new runtime scheduling dependency, process, or competing Playwright browser is introduced.
- **Priority**: Must
- **Related Stories**: US-120

### FR-5: Handle busy work, downtime, and missed slots without bursts

- **Description**: Due work must receive a bounded opportunity to run without compressing missed
  scheduled checks into a burst.
- **Acceptance Criteria**:
  - A due slot may be retried while it remains within the configured one-hour grace period if the
    global coordinator is busy.
  - A daemon restart may recover at most the newest unclaimed slot that is still within its grace
    period.
  - Slots older than the grace period are durably marked missed and are not executed.
  - If multiple slots are overdue, at most one is eligible for catch-up; older overdue slots are
    marked missed before dispatch.
  - An actual scheduled batch never starts less than the configured minimum spacing after that
    user's previous scheduled batch start. A violating slot remains pending only within its grace
    period and otherwise becomes missed.
  - Manual `/checknow` work can cause a scheduled slot to retry through the shared gate, but manual
    work does not itself satisfy, cancel, or reschedule the slot.
  - Missed work is visible in structured logs and schedule status; it does not create a synthetic
    booking-check failure result for work that never opened a booking check.
- **Priority**: Must
- **Related Stories**: US-120

### FR-6: Configure and migrate randomized scheduling safely

- **Description**: Schedule count, minimum spacing, and missed-run grace must be explicit,
  validated configuration with migration-safe handling of the legacy fixed interval.
- **Acceptance Criteria**:
  - `[schedule]` supports `checks_per_booking_per_day` with default `3`, `minimum_spacing` with default
    `"2h"`, and `missed_run_grace` with default `"1h"`.
  - Configuration rejects counts below one, non-positive spacing/grace, or a count/spacing
    combination that cannot fit within a 24-hour schedule.
  - The legacy `check_interval` field remains accepted during migration but no longer drives
    scheduled-check timing; startup emits one clear deprecation warning when it is present.
  - Generated example configuration, config inspection output, README/runbook instructions, and
    startup logs describe daily randomized scheduling rather than a fixed interval.
  - Config changes affect only newly generated future dates; already persisted slots remain stable.
- **Priority**: Must
- **Related Stories**: US-121

### FR-7: Expose caller-scoped schedule status and operational evidence

- **Description**: Users and operators must be able to understand when randomized work is planned
  and whether recent slots completed or were missed without exposing another user's schedule.
- **Acceptance Criteria**:
  - Telegram `/status` shows the caller's next planned scheduled slot, or a clear reason when none is
    currently planned.
  - `/status` never shows another user's planned time or slot lifecycle.
  - Owner aggregate status may report counts of planned, running, completed, and missed slots but not
    another user's detailed schedule unless an existing admin boundary explicitly permits it.
  - Logs include user identity, slot identity, planned time, admission outcome, terminal status, and
    lateness without secrets, session data, booking details, or process environments.
  - Scheduler lifecycle and health reporting remain compatible with the daemon watchdog.
- **Priority**: Must
- **Related Stories**: US-121

## Non-Functional Requirements

### NFR-1: Randomness and distribution

- Across a representative property test sample, generated slots always remain inside their assigned
  windows and satisfy the configured spacing invariant.
- With an unforced production random source, different users and dates are not systematically
  assigned identical times.
- Randomization is operational jitter, not a security control; tests evaluate invariants and gross
  distribution rather than promising cryptographic secrecy.

### NFR-2: Reliability and restart safety

- Repeated planning and restart recovery are idempotent at the SQLite boundary.
- No terminal slot can be executed twice.
- A stop request interrupts scheduler waiting promptly; existing bounded shutdown behavior remains
  intact during browser work.
- Database migration from schema v11 preserves all existing users, synchronized reservations,
  history, traces, opportunities, and sessions.

### NFR-3: Performance and capacity

- An idle dispatcher performs no browser work and uses an interruptible sleep until the next bounded
  planning/dispatch wake.
- Slot planning and due-slot selection use indexed SQLite queries and remain bounded by active-user
  and retained-slot counts.
- Terminal schedule retention is bounded so table growth is not proportional to total daemon
  lifetime.

### NFR-4: Security and privacy

- Schedule rows are caller-scoped internal metadata and do not weaken existing Telegram,
  Booking.com-session, reservation, or admin boundaries.
- Randomized scheduling adds no autonomous reservation authority and does not change the action
  guard or final human-action boundary.
- Logs and status output never disclose secrets, cookies, encrypted keys, full browser state, or
  foreign-user schedule details.

### NFR-5: Compatibility and verification

- Existing `/checknow`, account synchronization, daily limits, check history, savings alerts,
  current-opportunity lifecycle, and session recovery remain compatible.
- Focused slot-generation, persistence, migration, dispatcher, coordinator, status, shutdown, and
  restart tests pass.
- Full pytest, Ruff, mypy, AI-DLC artifact validation, status-integrity checks, and diff checks pass
  before handoff.
- A real VPS deployment and Booking.com/Telegram smoke test remain operational acceptance gates and
  require separate deployment approval.

## Constraints

### Technical Constraints

**Project-wide standards**: Required standards will be loaded from the memory-bank standards folder
by the Construction Agent.

**Intent-specific constraints**:

- Preserve the single-process, stdlib-first scheduler and existing `threading.Event` shutdown
  mechanism while amending ADR-006's fixed-interval decision.
- Preserve ADR-021's one coordinator and one non-blocking browser gate.
- Use SQLite schema migration and repository boundaries for durable slot lifecycle.
- Use UTC for schedule dates and stored timestamps.
- Keep one account synchronization per due user batch before booking checks.

### Business Constraints

- Three checks are a target for each continuously eligible booking on a fully available day, not a
  guarantee during downtime, authentication loss, Booking.com failure, quota exhaustion, or
  ineligibility.
- BookSaver remains Booking.com-hotel-only, self-hosted, owner/invite-only, and read-only with
  respect to reservation actions.

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| UTC is acceptable for the first randomized scheduler | Users may prefer local-day reporting | Keep timestamps explicit and plan per-user timezone support as a separate intent |
| One random slot per eight-hour window samples price changes better than three unconstrained draws | Booking.com price changes may follow a different pattern | Keep window/count configuration explicit and use operational evidence before tuning defaults |
| A one-hour grace balances short restarts against burst avoidance | Longer outages may miss a valuable check | Persist missed evidence and allow the grace to be configured |
| The existing default booking-check quota can cover three slots for supported booking counts | Operator-reduced quotas may prevent all checks | Enforce the quota, expose capped outcomes, and document the required relationship |
| Serialized browser work can finish due-user batches within their grace windows at expected scale | Many users or slow Booking.com responses may create missed slots | Preserve fairness evidence, measure lateness, and revisit capacity without adding concurrency implicitly |

## Open Questions

| Question | Owner | Due Date | Resolution |
|----------|-------|----------|------------|
| Are three checks applied per booking or divided across a user's bookings? | Product owner | 2026-08-01 | Resolved: each eligible booking participates in all three user slots |
| Should random draws be unconstrained across the day or broadly distributed? | Product owner | 2026-08-01 | Resolved: one random time in each broad eight-hour window |
| What timezone defines a schedule day? | Product owner | 2026-08-01 | Resolved: UTC for this intent |
| How should short downtime and coordinator contention be handled? | Product owner | 2026-08-01 | Resolved: one-hour grace, at most one catch-up, no bursts |
