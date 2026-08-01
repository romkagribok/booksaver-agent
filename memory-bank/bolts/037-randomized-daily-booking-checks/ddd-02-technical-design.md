---
stage: design
bolt: 037-randomized-daily-booking-checks
created: 2026-08-01T17:23:24Z
---

# Technical Design: Randomized Daily Booking Checks

## Architecture Pattern

Extend BookSaver's existing hexagonal, single-process daemon with a persisted scheduled-monitoring
domain and one adaptive dispatcher. The change preserves the existing `CheckCoordinator` as the
only browser-work admission boundary and preserves `threading.Event.wait()` as the scheduler's
interruptible wait mechanism.

The design deliberately separates:

1. Pure schedule settings, slot types, and random generation.
2. SQLite slot lifecycle and atomic transitions.
3. Planning/due-selection/dispatch orchestration.
4. Existing synchronized per-user monitoring execution.
5. CLI, Telegram, logs, and documentation presentation.

## Layer Structure

```text
Presentation
  CLI config/startup                 Telegram /status
         |                                  |
Application / Daemon
  DailySchedulePlanner -> RandomizedScheduleDispatcher -> Scheduler wait loop
                                     |
                                     v
                              CheckCoordinator
Domain                               |
  ScheduleSettings                   v
  ScheduledCheckSlot        existing sync/check/savings pipeline
  SlotIdentity/Status
  constrained slot generation
         |
Infrastructure
  SqliteScheduledCheckSlotRepository -> scheduled_check_slots (schema v12)
```

## Source Layout

- `src/booksaver/domain/schedule.py`
  - `ScheduleSettings`, `SlotIdentity`, `ScheduledCheckSlot`, `SlotStatus`, `MissReason`.
  - Pure `generate_daily_slots()` with injected `randbelow` and UTC validation.
- `src/booksaver/infrastructure/persistence/scheduled_check_slots.py`
  - Concrete SQLite repository and guarded transitions.
- `src/booksaver/application/schedule_dispatcher.py`
  - Daily planning, active-user horizon, recovery, due selection, retention, and next wake.
- `src/booksaver/daemon/scheduler.py`
  - Adaptive handler-returned wake times with a 60-second maximum discovery interval.
- `src/booksaver/daemon/check_coordinator.py`
  - Slot-specific non-blocking admission and exactly-one-user scheduled batch.
- Existing config, lifecycle, CLI, Telegram status, persistence schema/migration, and documentation
  files receive narrow integration changes.

## Domain Contracts

### ScheduleSettings

```python
@dataclass(frozen=True)
class ScheduleSettings:
    checks_per_booking_per_day: int = 3
    minimum_spacing: timedelta = timedelta(hours=2)
    missed_run_grace: timedelta = timedelta(hours=1)
```

Validation rejects non-positive values and `count * spacing >= 24h`; equality is rejected because it
leaves no random range.

### Random Generation

For ordinal `i` of `count`, window width is `24h / count`:

1. `window_start = UTC midnight + i * width`.
2. `window_end = UTC midnight + (i + 1) * width`.
3. `feasible_start = max(window_start, previous_planned_at + minimum_spacing)`.
4. Draw a whole-second offset uniformly from `[feasible_start, window_end)` with injected
   `randbelow(span_seconds)`.
5. Persist the resulting complete daily aggregate in one transaction.

The lower-bounded draw avoids unbounded rejection loops. The default remains random while ensuring
one time in each broad eight-hour window. The first window applies the prior persisted day's final
planned time as its lower boundary.

## Persistence Design

Schema v12 adds only schedule state:

```sql
CREATE TABLE scheduled_check_slots (
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    schedule_date TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    planned_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('planned','running','completed','missed')),
    started_at TEXT,
    finished_at TEXT,
    miss_reason TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, schedule_date, ordinal)
);

CREATE INDEX idx_scheduled_slots_due
    ON scheduled_check_slots(status, planned_at, user_id, ordinal);
CREATE INDEX idx_scheduled_slots_user_next
    ON scheduled_check_slots(user_id, status, planned_at);
```

Canonical UTC ISO timestamps preserve lexical ordering. The migration is additive and idempotent;
it preserves every schema-v11 table and row. Existing explicit user purge deletes schedule rows,
with the foreign key as defense in depth.

### Atomic Planning

`insert_daily_schedule()` uses `BEGIN IMMEDIATE`:

- Existing complete aggregate wins and is returned unchanged.
- No existing rows inserts every ordinal in the same transaction.
- A partial existing aggregate is treated as corruption and fails closed; it is never filled from a
  new random draw.

### Due Preparation

Within a transaction, `prepare_due(now, grace, spacing)`:

1. Recovers any `running` rows as `missed/recovered_running` on process startup.
2. Marks planned rows older than grace `missed/grace_expired`.
3. For multiple within-grace overdue rows per user, retains only the newest and marks older ones
   `missed/superseded_catch_up`.
4. Excludes inactive/revoked users and marks their pending rows `missed/user_unavailable`.
5. Returns candidates ordered by `(planned_at, user_id, ordinal)`.

### Claim Sequence

The concurrency sequence is mandatory:

```text
dispatcher selects planned slot
  -> coordinator acquires global gate non-blocking
      -> BUSY: return; slot remains planned
      -> ACQUIRED: repository atomically claims planned -> running
          -> sync exactly one user
          -> check every eligible booking through existing pipeline
          -> repository completes running -> completed in finally
      -> release global gate
```

The guarded claim revalidates:

- status is still planned;
- slot is due and within grace;
- user is still active;
- no newer overdue candidate supersedes it;
- no scheduled slot for that user started within `minimum_spacing`.

A process kill after claim leaves `running`; startup recovery marks it missed. An in-process batch
return or exception marks it completed because the scheduled attempt was admitted; booking/sync
failures remain recorded by their existing mechanisms.

## Coordinator Integration

Add `run_scheduled_slot(slot_identity) -> ScheduledAdmission`:

- `BUSY` and `STOPPING` occur before claim and leave the slot planned.
- `STALE` means guarded claim failed because state/access/time changed.
- `COMPLETED` means the user batch was admitted and returned.

Refactor global scheduled execution into `_run_scheduled_user_locked(store, user_id)`:

1. Resolve exactly one active user.
2. Synchronize that user's complete account inventory once.
3. Build the existing check plan with only that user and current daily counters.
4. Preserve skipped-cap history/notices.
5. Recheck active access before allowance and each fresh browser context.
6. Reuse existing monitor, trace, savings, notifier, auth-required, session, and LLM-budget paths.

Manual `/checknow` is unchanged and can only defer a scheduled slot through the shared gate.

## Dispatcher and Scheduler

### RandomizedScheduleDispatcher.run_once

1. Open local SQLite.
2. Load active users.
3. Ensure current and next UTC dates are planned for each active user.
4. Recover abandoned running rows once per process, prune old terminal rows, and prepare due slots.
5. Dispatch ordered candidates sequentially.
6. Stop the pass on `BUSY` because the global gate cannot admit later candidates either.
7. Return the earliest future planned time, or a 30-second busy retry.

### Scheduler.run

- Registered handlers return `datetime | None` for their next desired wake.
- The loop invokes handlers at startup for planning/recovery; no global user batch runs unless a
  persisted slot is legitimately due/catch-up eligible.
- The scheduler records the earliest next operational wake and waits interruptibly.
- Waits are capped at 60 seconds so newly invited users/configured state are discovered promptly.
- Past wake values clamp to a small nonzero delay to prevent a spin loop.
- Handler errors are logged and retried after the discovery interval without killing lifecycle
  supervision.

## Configuration Design

`Config` projects `ScheduleSettings`. `[schedule]` is optional and defaults to:

```toml
[schedule]
checks_per_booking_per_day = 3
minimum_spacing = "2h"
missed_run_grace = "1h"
```

Legacy behavior:

- A supplied `check_interval` is still syntax/minimum validated.
- Its value is ignored for slot timing.
- One visible migration warning is emitted per config load.
- If old and new keys coexist, new keys win and the warning explicitly says the old value is
  ignored.

Already persisted dates never change; settings apply when a date is first planned.

## Presentation and Privacy

- CLI init/example/show/startup output describes checks/day, spacing, grace, and UTC.
- `/status` resolves the stable caller first, opens a caller-scoped next-slot query, and renders the
  exact UTC instant or a clear no-plan explanation.
- Global scheduler wake time is no longer shown as a user's check time.
- Logs include stable user/slot identity, planned time, start lateness, status, and bounded reason,
  never cookies, secrets, booking facts, or process environments.

## Security Design

- Schedule persistence is local and user-keyed.
- Due and claim operations join/recheck active-user access.
- Caller-scoped reads require the already resolved local user identity.
- The single coordinator gate remains the concurrency and browser-pressure boundary.
- Reservation mutation authority, action guards, authenticated owner sessions, and equivalence rules
  are unchanged.

## NFR Implementation

- **Restart safety**: persisted plans, guarded lifecycle transitions, conservative running recovery.
- **Random distribution**: pure injected generator plus multi-seed invariant tests.
- **Performance**: two indexes, three rows/user/day by default, 30-day terminal retention, adaptive
  wait capped at 60 seconds.
- **Shutdown**: unchanged shared `threading.Event`; no uninterruptible sleep.
- **Compatibility**: additive v12 migration, legacy config parsing/warning, existing daily quota
  semantics.
- **Observability**: caller next-slot query and structured redacted lifecycle logs.

## Verification Design

1. Pure generation/config unit tests, including cross-midnight boundaries and many deterministic
   seeds.
2. SQLite migration, idempotent planning, atomic claim, recovery, catch-up, purge, and retention
   integration tests.
3. Scheduler/dispatcher tests for startup, busy retry, grace expiry, no burst, ordering, and stop.
4. Coordinator tests for exactly-one-user synchronization, every eligible booking, quotas,
   revocation, and gate-before-claim.
5. Caller-scoped Telegram status and CLI/config migration tests.
6. Full pytest, Ruff, mypy, artifact validation, status integrity, and diff checks.

## Design Risks and Shields

- **Claim before browser gate** → prohibited sequence and explicit busy regression test.
- **Infinite rejection sampling** → direct lower-bounded random interval.
- **Startup burst** → only within-grace newest catch-up per user; older rows missed.
- **Cross-user status leak** → query requires resolved stable user ID.
- **Quota multiplication** → documented per-booking accounting remains authoritative.
- **Timezone coupling** → schedule UTC is separate from browser-emulation timezone.
