---
stage: model
bolt: 037-randomized-daily-booking-checks
created: 2026-08-01T17:18:30Z
---

# Domain Model: Randomized Daily Booking Checks

## Bounded Context

The **Scheduled Monitoring** context decides when an active user's synchronized eligible bookings
receive ordinary scheduled monitoring. It owns slot planning and lifecycle only. Reservation truth,
eligibility, browser execution, quotas, check history, savings, notifications, and session state
remain owned by their existing contexts.

## Entities

### ScheduledCheckSlot

Represents one durable opportunity to execute one user-scoped scheduled batch.

Properties:

- `user_id`: stable local owner identity.
- `schedule_date`: UTC date whose equal-width window owns the slot.
- `ordinal`: zero-based window/slot index within the date.
- `planned_at`: exact randomized UTC instant inside the ordinal's window.
- `status`: `planned`, `running`, `completed`, or `missed`.
- `started_at`: actual scheduled-batch admission time when claimed.
- `finished_at`: terminal transition time.
- `miss_reason`: bounded operational reason for a missed terminal state.

Business rules:

1. `(user_id, schedule_date, ordinal)` is immutable and unique.
2. `planned_at` is timezone-aware UTC and belongs to the ordinal's equal-width daily window.
3. Valid transitions are `planned → running → completed` and `planned|running → missed`.
4. `completed` and `missed` are terminal and never reopen.
5. A recovered `running` slot becomes `missed`; it is never replayed.
6. Claiming records `started_at` atomically with the `running` transition.
7. Terminal states record `finished_at`; only `missed` records a reason.

### UserDailySchedule

Aggregate view of all slots for one user and UTC date.

Properties:

- `user_id`, `schedule_date`.
- Ordered `slots`, exactly `checks_per_booking_per_day` when planning is complete.
- Optional previous-date final slot boundary.

Business rules:

1. Ordinals are contiguous from zero.
2. Planned times are strictly increasing.
3. Adjacent planned times are at least `minimum_spacing` apart.
4. The first planned time respects the minimum from the previous date's last slot when present.
5. Replanning an already complete aggregate returns it unchanged.

## Value Objects

### ScheduleSettings

- `checks_per_booking_per_day`: integer, default 3, minimum 1.
- `minimum_spacing`: positive duration, default 2 hours.
- `missed_run_grace`: positive duration, default 1 hour.
- `retention_days`: positive bounded operational retention.

Constraints:

- `checks_per_booking_per_day × minimum_spacing <= 24 hours`.
- Window width is `24 hours / checks_per_booking_per_day`.
- Values are immutable after config projection; persisted existing dates do not change.

### SlotIdentity

Value equality over `user_id`, `schedule_date`, and `ordinal`.

### SlotWindow

Half-open UTC range for one ordinal: `[date + ordinal × width, date + (ordinal + 1) × width)`.

### SlotStatus

Closed enumeration of `planned`, `running`, `completed`, and `missed`.

### MissReason

Bounded enumeration/string values for `grace_expired`, `superseded_catch_up`,
`spacing_conflict`, `recovered_running`, `user_unavailable`, and `stopping`.

### ScheduledAdmission

Result of asking the existing coordinator to run due users: `accepted`, `busy`, `stopping`, or
`unavailable`. It is distinct from an individual booking-check result.

## Aggregate Invariants

The `UserDailySchedule` is the aggregate root for planning; `ScheduledCheckSlot` is the aggregate
root for atomic execution lifecycle.

1. Planning is insert-if-absent and idempotent.
2. Random choice occurs only before persistence.
3. At most one recoverable overdue slot per user may be claimed; older overdue planned slots become
   missed first.
4. A due slot is claimable only when `planned_at <= now <= planned_at + grace` and the prior actual
   scheduled start is at least `minimum_spacing` earlier.
5. A slot outside grace or unable to satisfy spacing before grace expiry becomes missed.
6. A slot completes after its user-scoped scheduled batch returns, including a conclusive no-work
   batch with no eligible bookings. Individual booking failures remain ordinary check outcomes.

## Domain Services

### DailySchedulePlanner

Operations:

- `ensure_planned(user_id, schedule_date, settings) -> UserDailySchedule`
- `ensure_horizon(active_user_ids, today, settings) -> sequence[UserDailySchedule]`

Algorithmic rules:

1. Divide the UTC day into equal half-open windows.
2. Draw an exact instant independently inside each window using an injected random source.
3. Reject/redraw candidates that violate adjacent or cross-date spacing.
4. Persist the complete schedule atomically; a uniqueness race reads the winner.

### DueSlotSelector

Operations:

- `prepare_due(now, settings) -> ordered slots`
- `next_planned(user_id, now) -> slot | None`

Rules:

1. Recover abandoned running slots as missed.
2. Mark expired or superseded overdue planned slots missed.
3. Retain only the newest within-grace candidate per user.
4. Order candidates by planned time then stable user identity.
5. Claim one slot only through the repository's atomic transition.

### RandomizedScheduleDispatcher

Operations:

- `run_once(now) -> DispatchSummary`
- `seconds_until_next_wake(now) -> bounded duration`

Rules:

1. Plan the current and next UTC date for active users.
2. Ask `DueSlotSelector` for bounded due work.
3. Request one user-scoped batch through the existing coordinator.
4. Busy leaves a slot planned inside grace; accepted claims and then completes/misses according to
   the coordinator outcome.
5. Stop requests abort new admission and preserve prompt shutdown.

## Repository Interfaces

### ScheduledCheckSlotRepository

- `list_for_user_date(user_id, date) -> sequence[ScheduledCheckSlot]`
- `insert_daily_schedule(schedule) -> UserDailySchedule`
- `last_planned_before(user_id, instant) -> ScheduledCheckSlot | None`
- `list_due(now, grace) -> sequence[ScheduledCheckSlot]`
- `claim(identity, now, minimum_spacing) -> ScheduledCheckSlot | None`
- `complete(identity, now) -> bool`
- `miss(identity, now, reason) -> bool`
- `recover_running(now) -> int`
- `mark_expired_and_superseded(now, grace) -> int`
- `next_planned_for_user(user_id, now) -> ScheduledCheckSlot | None`
- `prune_terminal(before) -> int`

Repository invariants:

- Mutating transitions use guarded SQL inside transactions.
- User deletion cascades slot deletion.
- Due and caller-next queries are indexed.
- Repository methods never expose another user's detailed plan through presentation adapters.

## Domain Events and Operational Signals

- **DailySchedulePlanned**: user/date, slot count; no booking data.
- **ScheduledSlotClaimed**: slot identity, planned time, actual start, lateness.
- **ScheduledSlotCompleted**: slot identity, finish time.
- **ScheduledSlotMissed**: slot identity, finish time, bounded reason.
- **ScheduledSlotDeferredBusy**: slot identity and remaining grace; no terminal transition.

These are structured log concepts, not a new event bus.

## Ubiquitous Language

- **Daily slot**: Persisted randomized opportunity for one user's scheduled batch.
- **User batch**: One account synchronization followed by ordinary checks for every currently
  eligible booking owned by that user.
- **Booking check**: One existing monitor execution for one booking; daily quotas count these, not
  user batches.
- **Broad window**: One equal portion of a UTC day used to distribute random selections.
- **Planned spacing**: Minimum time between persisted randomized slot instants.
- **Actual spacing**: Minimum time between actual starts of a user's scheduled batches.
- **Grace**: Bounded time after `planned_at` during which one slot may still be admitted.
- **Catch-up**: Admission of the newest overdue slot still within grace; never more than one per
  user and never a replay burst.
- **Missed**: Terminal slot that did not open its scheduled user batch.

## Story Coverage

- **US-119**: Slot, schedule aggregate, settings, planner, repository, lifecycle, and recovery.
- **US-120**: Selector, dispatcher, coordinator admission, batch semantics, grace, spacing, fairness.
- **US-121**: Settings projection, caller-scoped next-slot query, and operational signals.
