---
unit: 001-randomized-daily-booking-checks
intent: 020-randomized-daily-booking-checks
phase: inception
status: complete
unit_type: cli
default_bolt_type: ddd-construction-bolt
created: 2026-08-01T17:14:32.000Z
updated: 2026-08-01T17:14:32.000Z
---

# Unit Brief: Randomized Daily Booking Checks

## Purpose

Replace the fixed global interval with durable per-user random daily slots that check every eligible
booking three broadly distributed times per available UTC day while retaining BookSaver's one
serialized browser and authenticated synchronization boundaries.

## Scope

### In Scope

- Generate constrained random per-user UTC slots and persist them once.
- Atomically claim, complete, miss, recover, retain, and purge slot lifecycle state.
- Dispatch due user batches through the existing coordinator with bounded busy retry.
- Preserve one inventory synchronization per user slot and ordinary per-booking monitoring.
- Migrate schedule config, lifecycle/status output, documentation, and tests.

### Out of Scope

- Per-user timezones, concurrent browsers, a second scheduler, cron/APScheduler, or distributed work.
- Changes to manual `/checknow`, daily quota semantics, eligibility, price equivalence, or alerts.
- Autonomous Booking.com reservation actions or deployment without separate approval.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Generate random, broadly distributed daily slots | Must |
| FR-2 | Check every eligible booking at each due user slot | Must |
| FR-3 | Persist schedule lifecycle and suppress duplicate execution | Must |
| FR-4 | Dispatch due users through the existing coordinator | Must |
| FR-5 | Handle busy work, downtime, and missed slots without bursts | Must |
| FR-6 | Configure and migrate randomized scheduling safely | Must |
| FR-7 | Expose caller-scoped schedule status and operational evidence | Must |

## Domain Concepts

### Key Entities

| Entity | Description | Attributes |
|--------|-------------|------------|
| `ScheduledCheckSlot` | Durable user-level opportunity to synchronize and check every eligible booking | user ID, UTC date, ordinal, planned time, status, attempt/completion timestamps |
| `UserDailySchedule` | Ordered slots for one user and UTC date | user ID, date, slot collection, previous-day boundary |

### Key Value Objects

| Value Object | Description | Invariants |
|--------------|-------------|------------|
| `ScheduleSettings` | Validated scheduling policy | count >= 1, positive spacing/grace, feasible within 24h |
| `SlotIdentity` | Stable durable identity | user/date/ordinal unique |
| `SlotStatus` | Slot lifecycle | planned, running, completed, missed; terminal states do not reopen |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `plan_day` | Randomly create one slot per equal UTC-day window with spacing | user, date, settings, prior boundary, RNG | persisted daily schedule |
| `claim_due` | Select and atomically claim bounded due work | now, grace, spacing | zero or one newest recoverable slot per user |
| `complete_or_miss` | Record terminal outcome without replay | slot identity, outcome time/reason | terminal slot |
| `run_scheduled_for_users` | Synchronize and check eligible bookings for due users | ordered user IDs | ordinary monitoring outcomes |
| `next_slot_for_user` | Read caller-scoped status | user ID, now | next planned slot or none reason |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 3 |
| Must Have | 3 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-119 | Plan durable random daily slots | Must | Planned |
| US-120 | Dispatch due booking checks safely | Must | Planned |
| US-121 | Configure and observe randomized scheduling | Must | Planned |

## Dependencies

### Depends On

| Unit | Reason |
|------|--------|
| `019/001-booking-account-sync-core` | Supplies authoritative synchronized reservation state |
| `019/002-synchronized-booking-interface` | Requires one synchronization before each scheduled batch |
| Existing core scheduler/coordinator | Owns interruptible daemon lifecycle and serialized browser work |

### Depended By

| Unit | Reason |
|------|--------|
| Future schedule tuning | Can build on durable slot evidence and policy seams |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| Booking.com mobile web | Read-only inventory and price checks | High: authentication, availability, bot defenses |
| Telegram Bot API | Caller-scoped status and alerts | Low: existing adapter only |
| Local SQLite | Slot persistence and atomic claim | Medium: migration and crash recovery |

## Technical Context

### Suggested Technology

Python 3.11 stdlib `datetime`, `random.SystemRandom`, `threading.Event`, and `sqlite3`; existing
hexagonal repository patterns, coordinator, configuration loader, and Telegram command adapter.

### Integration Points

| Integration | Type | Protocol |
|-------------|------|----------|
| Scheduler → dispatcher | Application call | Python method |
| Dispatcher → slot repository | Repository | SQLite transaction |
| Dispatcher → coordinator | Application call | Python method |
| Telegram `/status` → schedule query | Read adapter | Python method |

### Data Storage

| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| Scheduled slots | SQLite | Three rows/user/day by default | Bounded terminal history |

## Constraints

- Persist UTC timestamps and keep random-source/clock injection explicit.
- Preserve ADR-021's one coordinator and browser gate.
- Amend ADR-006 without adding a scheduling dependency.
- Never replay an indeterminate running slot after restart.
- Keep actual scheduled batch starts at least two hours apart per user.
- Three checks remain conditional on eligibility, availability, authentication, and quota.

## Success Criteria

### Functional

- [ ] Three random, broad, separated slots persist per active user/day by default.
- [ ] Every eligible booking participates once in every admitted user slot.
- [ ] Restart, busy work, and downtime never cause duplicate or burst execution.
- [ ] Configuration and caller-scoped `/status` reflect randomized schedules.

### Non-Functional

- [ ] Slot queries are indexed and retention bounded.
- [ ] Shutdown remains prompt and browser work serialized.
- [ ] Privacy, session, quota, and reservation-action boundaries are unchanged.

### Quality

- [ ] Focused scheduling, persistence, coordinator, config, and status tests pass.
- [ ] Full pytest, Ruff, mypy, artifact validation, status integrity, and diff checks pass.
- [ ] Code and test diff is presented before commit or merge.

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| `037-randomized-daily-booking-checks` | DDD | US-119, US-120, US-121 | Deliver durable random scheduling end to end |

## Notes

The product owner explicitly authorized continuous AI-DLC progression through code and test
creation. Commit, merge, deployment, and external smoke actions remain separately gated.
