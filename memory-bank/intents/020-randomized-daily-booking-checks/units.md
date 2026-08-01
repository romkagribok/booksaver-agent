---
intent: 020-randomized-daily-booking-checks
phase: inception
status: units-decomposed
updated: 2026-08-01T17:14:32Z
---

# Randomized Daily Booking Checks - Unit Decomposition

## Requirement-to-Unit Mapping

- **FR-1**: Generate random, broadly distributed daily slots → `001-randomized-daily-booking-checks`
- **FR-2**: Check every eligible booking at each due user slot → `001-randomized-daily-booking-checks`
- **FR-3**: Persist schedule lifecycle and suppress duplicate execution → `001-randomized-daily-booking-checks`
- **FR-4**: Dispatch due users through the existing coordinator → `001-randomized-daily-booking-checks`
- **FR-5**: Handle busy work, downtime, and missed slots without bursts → `001-randomized-daily-booking-checks`
- **FR-6**: Configure and migrate randomized scheduling safely → `001-randomized-daily-booking-checks`
- **FR-7**: Expose caller-scoped schedule status and operational evidence → `001-randomized-daily-booking-checks`

Each functional requirement is assigned exactly once.

## Units Overview

This intent decomposes into one cohesive CLI-daemon unit of work.

### Unit 1: 001-randomized-daily-booking-checks

**Description**: Own constrained random slot planning, durable lifecycle, due-user dispatch through
the existing coordinator, configuration migration, caller-scoped status, and verification.

**Stories**:

- `001-plan-durable-random-daily-slots`: Generate and persist restart-safe randomized slots.
- `002-dispatch-due-booking-checks-safely`: Check every due eligible booking without bursts or
  concurrent browsers.
- `003-configure-and-observe-randomized-scheduling`: Migrate configuration and expose safe schedule
  status and operational evidence.

**Deliverables**:

- Domain schedule types and planner/dispatcher services.
- Additive SQLite slot schema, migration, and repository.
- Coordinator/lifecycle wiring for user-scoped scheduled batches.
- Configuration, CLI/Telegram status, documentation, and tests.
- ADR-029 amending ADR-006 while preserving ADR-021.

**Dependencies**:

- Depends on: Existing synchronized booking interface, `CheckCoordinator`, per-user limits,
  scheduler lifecycle, SQLite migrations, and Telegram status boundary.
- Depended by: Future schedule tuning or per-user timezone work.

**Estimated Complexity**: L

## Unit Dependency Graph

```text
[Existing scheduler + synchronization + coordinator]
                         |
                         v
       [001-randomized-daily-booking-checks]
```

## Execution Order

1. Model slot lifecycle and invariants.
2. Design persistence, dispatch, configuration, and status integration.
3. Record the adaptive-scheduler ADR amendment.
4. Implement the single planned construction bolt.
5. Verify focused behavior and the full repository gate.
