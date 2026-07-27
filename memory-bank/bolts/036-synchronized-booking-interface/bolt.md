---
id: 036-synchronized-booking-interface
unit: 002-synchronized-booking-interface
intent: 019-booking-account-synchronization
type: ddd-construction-bolt
status: complete
stories:
  - 001-synchronize-every-freshness-boundary
  - 002-show-every-reservation-and-reason
  - 003-remove-manual-mutation-and-rebook
created: 2026-07-27T16:28:04.000Z
started: 2026-07-27T17:02:20.000Z
completed: "2026-07-27T17:02:35Z"
current_stage: null
stages_completed:
  - name: model
    completed: 2026-07-27T17:02:22.000Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-27T17:02:25.000Z
    artifact: ddd-02-technical-design.md
  - name: implement
    completed: 2026-07-27T17:02:30.000Z
    artifact: coordinator, Telegram, CLI, and documentation changes
  - name: test
    completed: 2026-07-27T17:02:34.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 035-booking-account-sync-core
enables_bolts: []
requires_units:
  - 001-booking-account-sync-core
blocks: true
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 036-synchronized-booking-interface

## Objective

Integrate synchronization with every approved trigger, make `/bookings` the complete read-only
reservation view, and remove manual CRUD and guided rebooking from Telegram, CLI, and documentation.

## Stories Included

- **US-116**: Synchronize every freshness boundary (Must)
- **US-117**: Show every reservation and reason (Must)
- **US-118**: Remove manual mutation and guided rebooking (Must)

## Stages

- [x] **1. Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. Implement**: Complete → orchestration/Telegram/CLI/docs changes
- [x] **4. Test**: Complete → `ddd-03-test-report.md`

## Dependencies

### Requires
- `035-booking-account-sync-core`
- Unit `001-booking-account-sync-core`

### Enables
- Final pre-merge verification.

## Success Criteria

- [x] `/connect`, schedule, `/checknow`, and `/bookings` synchronize safely.
- [x] `/bookings` shows complete lifecycle/eligibility without mutation actions.
- [x] Retired commands are absent and unknown.
- [x] Savings remain informational with no guided-rebook session.
- [x] Documentation and full quality gates pass.
