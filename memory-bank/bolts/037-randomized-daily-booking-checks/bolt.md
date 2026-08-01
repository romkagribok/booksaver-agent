---
id: 037-randomized-daily-booking-checks
unit: 001-randomized-daily-booking-checks
intent: 020-randomized-daily-booking-checks
type: ddd-construction-bolt
status: complete
stories:
  - 001-plan-durable-random-daily-slots
  - 002-dispatch-due-booking-checks-safely
  - 003-configure-and-observe-randomized-scheduling
created: 2026-08-01T17:17:15.000Z
started: 2026-08-01T17:18:11.000Z
completed: "2026-08-01T17:40:40Z"
current_stage: null
stages_completed:
  - name: model
    completed: 2026-08-01T17:18:30.000Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-08-01T17:23:24.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-01T17:24:48.000Z
    artifact: adr-029-persisted-random-daily-scheduling.md
  - name: implement
    completed: 2026-08-01T17:38:30.000Z
    artifact: src/booksaver/domain/schedule.py
  - name: test
    completed: 2026-08-01T17:39:57.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 036-synchronized-booking-interface
enables_bolts: []
requires_units:
  - 002-synchronized-booking-interface
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 037-randomized-daily-booking-checks

## Overview

Replace BookSaver's fixed global interval with persisted, broadly distributed, constrained random
daily slots for each user and route due booking checks through the existing serialized coordinator.

## Objective

Deliver restart-safe random daily schedule planning, atomic slot lifecycle, bounded missed-run
handling, per-user due dispatch, config migration, caller-scoped visibility, documentation, and
comprehensive tests without changing Booking.com or human-action safety boundaries.

## Stories Included

- **US-119**: Plan durable random daily slots (Must)
- **US-120**: Dispatch due booking checks safely (Must)
- **US-121**: Configure and observe randomized scheduling (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. ADR Analysis**: Complete → `adr-029-persisted-random-daily-scheduling.md`
- [x] **4. Implement**: Complete → domain/application/infrastructure/adapters/docs
- [x] **5. Test**: Complete → tests and `ddd-03-test-report.md`

## Dependencies

### Requires

- `036-synchronized-booking-interface` (complete)
- Existing scheduler, `CheckCoordinator`, SQLite migration, config, and Telegram status boundaries.

### Enables

- Operational rollout and future evidence-based schedule tuning.

## Success Criteria

- [x] Three constrained random daily slots persist per active user by default.
- [x] Every continuously eligible booking participates once per admitted slot.
- [x] Restarts, downtime, and busy work do not duplicate or burst checks.
- [x] One coordinator/browser boundary, quotas, sessions, and synchronization remain authoritative.
- [x] Config, status, logs, docs, and migration behavior are coherent.
- [x] Focused and full repository verification passes.
- [x] Code/test diff is ready to present before commit or merge.

## Notes

The product owner approved continuous progression through code and test creation. Human checkpoints
remain documented in the stage artifacts; commit, merge, deployment, and external smoke tests are
not authorized by this bolt execution.
