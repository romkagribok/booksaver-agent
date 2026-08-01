---
bolt: 037-randomized-daily-booking-checks
created: 2026-08-01T17:24:48Z
status: accepted
superseded_by: null
---

# ADR-029: Persisted Random Daily Scheduling

## Context

ADR-006 selected an interruptible `threading.Event.wait(timeout)` loop for one fixed-interval MVP
job. BookSaver now serves multiple invited users, synchronizes each authenticated Booking.com
inventory before monitoring, and must sample prices at different times of day. A single global fixed
interval runs every user together, drifts by batch duration, runs immediately after every restart,
and cannot guarantee broad daily coverage or duplicate-safe random jitter.

The existing one-process, stdlib-first architecture and ADR-021's single non-blocking browser gate
remain valuable. The new schedule must not introduce another scheduler, concurrent Playwright work,
or a dependency merely to obtain jitter.

## Decision

Replace fixed global interval scheduling with persisted per-user random daily slots:

1. Split each UTC day into equal windows and select one constrained random instant per window for
   each active user; default to three windows/check opportunities and two-hour spacing.
2. Persist the full slot plan and lifecycle in SQLite before execution so restarts cannot reroll or
   duplicate work.
3. Retain `threading.Event.wait(timeout)` but make its timeout adaptive to the earliest durable due
   slot, with a bounded discovery interval for new users and state.
4. Dispatch one due user at a time through the existing `CheckCoordinator`. Acquire ADR-021's browser
   gate before atomically claiming the slot; busy work leaves the slot planned for retry inside its
   one-hour grace.
5. Recover abandoned running slots as missed, permit at most the newest within-grace catch-up, and
   never replay multiple missed slots in a burst.
6. Treat one admitted slot as one user batch: synchronize once, then check every currently eligible
   booking using existing quota, browser, history, savings, session, and notification behavior.

ADR-029 supersedes ADR-006's fixed-interval premise while retaining its interruptible stdlib wait
mechanism. It amends ADR-021 only for scheduled retry semantics: a busy due slot remains retryable
within bounded grace instead of disappearing until a global next interval. The single gate and
non-queued manual-check behavior remain unchanged.

## Rationale

Durable constrained random slots directly satisfy time-of-day coverage and restart safety. One
random draw inside each broad window produces better sampling than three unconstrained draws, which
can legally cluster in a small part of the day. SQLite is already BookSaver's local durable state and
can enforce identity and atomic lifecycle without another service or runtime dependency.

Acquiring the coordinator gate before claim is the critical concurrency rule: `/checknow` contention
then leaves the slot planned rather than manufacturing a running slot that would later recover as
missed. Serial user batches preserve the proven session, browser-pressure, and SQLite boundaries.

### Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| Add random jitter to the global interval | Very small code change | Users remain aligned; drift/restarts alter daily count; no broad coverage or durable identity | Does not meet per-user or restart requirements |
| Draw three unconstrained random daily instants | Simple random model | Legal clustering can leave most of a day unsampled | Broad windows provide materially better coverage |
| Keep slots only in memory | No schema migration | Restart rerolls, duplicates, loses completion evidence, and enables bursts | VPS restarts are normal and must be safe |
| Derive deterministic slots from user/date | Restart-stable without plans | Requires stable seed policy and still needs durable execution suppression | Persisted real randomness is clearer and more observable |
| APScheduler or cron | Built-in jitter/misfire features | New dependency/process concepts; per-user dynamic persistence and coordinator claim ordering still required | Existing stdlib/SQLite boundaries are sufficient |
| Concurrent user browsers | Higher throughput | Higher Booking.com/IP pressure, memory/session risk, and conflicts with ADR-021 | Expected self-hosted scale does not justify the risk |
| Replay all missed slots after restart | Maximizes nominal count | Creates burst traffic and closely spaced checks | Violates coverage and safety goal |

## Consequences

### Positive

- Continuously eligible bookings receive three broadly distributed daily opportunities by default.
- User schedules are independently random and do not move after restart.
- Duplicate suppression, missed evidence, and caller-specific next-run status are durable.
- No new runtime dependency, process, or concurrent browser is introduced.
- Existing synchronization, quotas, sessions, monitoring, savings, and action boundaries are reused.

### Negative

- Adds schema-v12 schedule state, migration, retention, and recovery logic.
- Three slots multiply per-booking daily quota use; operators with reduced caps may see capped work.
- Serial browser work can miss a slot at larger user counts; lateness/miss evidence is required before
  considering concurrency.
- UTC may be less intuitive than a user's local day; timezone preferences remain future scope.

### Risks

- **False missed work on contention**: acquire the browser gate before atomic claim and regression
  test busy `/checknow`.
- **Cross-midnight clustering**: generate tomorrow against today's final persisted planned instant.
- **Startup burst**: only the newest within-grace slot can catch up; older overdue slots become
  terminal missed.
- **Foreign schedule disclosure**: `/status` queries only after stable caller resolution.
- **Unbounded state growth**: prune only old terminal rows with indexed queries and bounded retention.

## Related

- **Stories**: US-119, US-120, US-121
- **Standards**: system architecture, tech stack, coding standards
- **Previous ADRs**: ADR-006 (superseded fixed interval; retained Event wait), ADR-008 (synchronous
  Playwright), ADR-021 (single coordinator/browser gate), ADR-027/028 (authoritative complete account
  synchronization)
