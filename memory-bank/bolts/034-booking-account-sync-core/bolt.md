---
id: 034-booking-account-sync-core
unit: 001-booking-account-sync-core
intent: 019-booking-account-synchronization
type: ddd-construction-bolt
status: complete
stories:
  - 001-discover-complete-authenticated-inventory
  - 002-reconcile-remote-snapshots-atomically
  - 003-explain-eligibility-and-price-boundary
created: 2026-07-27T16:28:04.000Z
started: 2026-07-27T16:31:51.000Z
completed: "2026-07-27T17:01:31Z"
current_stage: null
stages_completed:
  - name: model
    completed: 2026-07-27T16:32:57.000Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-27T16:33:44.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-07-27T16:34:34.000Z
    artifact: adr-027-account-inventory-authoritative-projection.md, adr-028-completeness-gated-reconciliation.md
  - name: implement
    completed: 2026-07-27T16:57:00.000Z
    artifact: source implementation
  - name: test
    completed: 2026-07-27T17:00:55.000Z
    artifact: ddd-03-test-report.md
requires_bolts: []
enables_bolts:
  - 035-booking-account-sync-core
requires_units: []
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 3
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 034-booking-account-sync-core

## Objective

Prove a bounded read-only Booking.com inventory seam and implement the remote identity,
completeness, reconciliation, and eligibility domain needed for synchronized snapshots.

## Stories Included

- **US-112**: Discover complete authenticated inventory (Must)
- **US-113**: Reconcile remote snapshots atomically (Must)
- **US-114**: Explain eligibility and preserve price boundaries (Must)

## Stages

- [x] **1. Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. Implement**: Complete → domain/application/browser adapter changes
- [x] **4. Test**: Complete → `ddd-03-test-report.md`

## Dependencies

### Requires
- Existing ADR-004/007/008/013/016/021/024/025/026 infrastructure.

### Enables
- `035-booking-account-sync-core`

## Success Criteria

- [x] Read-only adapter seam has conclusive completeness evidence.
- [x] Domain and application reconciliation are deterministic and caller-scoped.
- [x] Eligibility is reason-coded and live-price source separation is preserved.
- [x] Targeted tests pass.
