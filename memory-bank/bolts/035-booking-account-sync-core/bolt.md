---
id: 035-booking-account-sync-core
unit: 001-booking-account-sync-core
intent: 019-booking-account-synchronization
type: ddd-construction-bolt
status: complete
stories:
  - 004-cut-over-legacy-and-recover-failures
created: 2026-07-27T16:28:04.000Z
started: 2026-07-27T17:01:20.000Z
completed: "2026-07-27T17:01:59Z"
current_stage: null
stages_completed:
  - name: model
    completed: 2026-07-27T17:01:30.000Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-27T17:01:45.000Z
    artifact: ddd-02-technical-design.md
  - name: implement
    completed: 2026-07-27T17:01:55.000Z
    artifact: schema and persistence implementation
  - name: test
    completed: 2026-07-27T17:01:58.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 034-booking-account-sync-core
enables_bolts:
  - 036-synchronized-booking-interface
requires_units: []
blocks: true
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 035-booking-account-sync-core

## Objective

Complete durable synchronized-inventory persistence, destructive legacy-booking cutover, redacted
run audit, and safe failure/restart semantics.

## Stories Included

- **US-115**: Cut over legacy state and recover from failures (Must)

## Stages

- [x] **1. Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. Implement**: Complete → schema/repository/application changes
- [x] **4. Test**: Complete → `ddd-03-test-report.md`

## Dependencies

### Requires
- `034-booking-account-sync-core`

### Enables
- `036-synchronized-booking-interface`

## Success Criteria

- [x] Migration removes only legacy booking-scoped data and is idempotent.
- [x] Atomic reconciliation and run audit survive conflicts/restarts.
- [x] Failure outcomes cannot create false absence.
- [x] Targeted migration/persistence tests pass.
