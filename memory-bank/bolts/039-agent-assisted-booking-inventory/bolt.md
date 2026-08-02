---
id: 039-agent-assisted-booking-inventory
unit: 002-agent-assisted-booking-inventory
intent: 021-booking-browser-llm-recovery
type: ddd-construction-bolt
status: complete
stories:
  - 001-recover-complete-booking-inventory-discovery
  - 002-preserve-completeness-and-safety-under-agent-assistance
  - 003-explain-and-observe-inventory-recovery
created: 2026-08-02T18:07:49.000Z
started: 2026-08-02T18:41:40.000Z
completed: "2026-08-02T19:25:34Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-08-02T18:41:40.000Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-02T18:41:40.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-02T18:41:40.000Z
    artifact: skipped-adr-030-and-adrs-027-028-govern
  - name: implement
    completed: 2026-08-02T19:23:30.000Z
  - name: test
    completed: 2026-08-02T19:24:50.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 038-shared-booking-browser-recovery
  - 034-booking-account-sync-core
  - 035-booking-account-sync-core
  - 036-synchronized-booking-interface
enables_bolts: []
requires_units:
  - 001-shared-booking-browser-recovery
  - 001-booking-account-sync-core
  - 002-synchronized-booking-interface
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 3
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 039-agent-assisted-booking-inventory

## Overview

Apply the shared progress-aware recovery controller and a typed inventory interpreter to
authenticated Booking.com account discovery used by `/bookings`, post-connect, `/checknow`, and
scheduled synchronization.

## Objective

Recover supported navigation/layout drift while preserving caller-scoped sessions and usage,
stable identity, deterministic completeness authority, partial-run reconciliation, read-only
safety, redacted observability, and accurate Telegram freshness outcomes.

## Stories Included

- **US-126**: Recover complete booking inventory discovery (Must)
- **US-127**: Preserve completeness and safety under agent assistance (Must)
- **US-128**: Explain and observe inventory recovery (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. ADR Analysis**: Skipped → ADR-030 and ADRs 027–028 govern
- [x] **4. Implement**: Complete → inventory recovery source, wiring, UX, docs
- [x] **5. Test**: Complete → tests and `ddd-03-test-report.md`

## Dependencies

### Requires

- `038-shared-booking-browser-recovery`.
- Existing account synchronization bolts 034–036 and ADRs 027–028.

### Enables

- Pre-merge review and later VPS acceptance of resilient account discovery.

## Success Criteria

- [x] Healthy deterministic discovery uses zero LLM calls.
- [x] Recoverable inventory drift invokes caller-scoped bounded recovery.
- [x] Assisted positive observations validate without invented identity.
- [x] Model output cannot prove completeness or archive unseen reservations.
- [x] All freshness triggers use the shared fallback-capable path.
- [x] `/bookings` and audit outcomes are accurate, redacted, and caller-scoped.
- [x] Focused and full repository checks pass.

## Notes

This bolt begins only after bolt 038 completes. It does not authorize human login automation,
provider additions, commit, push, PR, merge, deployment, or production live-model testing.
