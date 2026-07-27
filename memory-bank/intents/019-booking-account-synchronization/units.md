---
intent: 019-booking-account-synchronization
phase: inception
status: units-decomposed
updated: 2026-07-27T16:28:04Z
---

# Booking Account Synchronization - Unit Decomposition

## Units Overview

### Unit 1: `001-booking-account-sync-core`

**Description**: Discover, validate, classify, persist, and reconcile caller-owned Booking.com hotel
reservations as authoritative synchronized snapshots.

**Assigned Requirements**: FR-1, FR-2, FR-3, FR-5, FR-6, FR-10, FR-11.

**Deliverables**:

- Read-only inventory port and Booking.com browser adapter.
- Remote reservation identity, lifecycle, completeness, eligibility, and synchronization domain.
- Atomic SQLite reconciliation and destructive legacy-booking cutover.
- Redacted synchronization audit and failure outcomes.

**Dependencies**: Existing session vault, browser coordinator, Booking repository, savings currentness,
authenticated search, and schema migration framework.

### Unit 2: `002-synchronized-booking-interface`

**Description**: Run synchronization at approved freshness boundaries, present all reservations
through `/bookings`, and remove manual booking mutation and guided-rebook behavior.

**Assigned Requirements**: FR-4, FR-7, FR-8, FR-9.

**Deliverables**:

- `/connect`, scheduled, `/checknow`, and `/bookings` trigger orchestration.
- Synchronized reservation inventory and eligibility UI.
- Removal of `/register`, `/editbooking`, `/deletebooking`, `/rebook`, their callbacks/dialogs, and
  normal CLI booking mutation.
- Updated help, command publication, runbook, and product documentation.

**Dependencies**: `001-booking-account-sync-core`.

## Requirement-to-Unit Mapping

- FR-1, FR-2, FR-3, FR-5, FR-6, FR-10, FR-11 → `001-booking-account-sync-core`
- FR-4, FR-7, FR-8, FR-9 → `002-synchronized-booking-interface`

Every functional requirement is assigned exactly once.

## Unit Dependency Graph

```text
[001-booking-account-sync-core] ──> [002-synchronized-booking-interface]
```

## Execution Order

1. Prove account-inventory feasibility and implement the synchronization core.
2. Complete persistence cutover and failure semantics.
3. Integrate triggers/UI and remove obsolete flows.
