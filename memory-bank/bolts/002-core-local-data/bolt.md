---
id: 002-core-local-data
unit: 001-core-local-data
intent: 001-booksaver-agent-mvp
type: ddd-construction-bolt
status: complete
stories:
  - 001-run-booksaver-as-a-local-daemon
created: 2026-06-16T16:25:59.000Z
started: 2026-06-17T21:10:00.000Z
completed: "2026-07-05T17:20:26Z"
current_stage: null
stages_completed: []
requires_bolts:
  - 001-core-local-data
enables_bolts: []
requires_units: []
blocks: true
complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: 002-core-local-data

## Overview

Second bolt for Unit 001. Adds the runtime layer on top of the data/config foundation:
running BookSaver as a local background daemon that starts and stops cleanly, and a
scheduler that fires checks on the user-configured interval. Provides the `Scheduler` hook
that Unit 2 will register browser-check jobs against.

## Objective

Start and stop BookSaver as a local background process (not a remote service) without
corrupting local state, and run scheduled jobs according to the configured interval,
exposing a scheduler hook for downstream units.

## Stories Included

- **US-001**: Run BookSaver as a local daemon (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [ ] **1. Domain Model**: Pending → ddd-01-domain-model.md
- [ ] **2. Technical Design**: Pending → ddd-02-technical-design.md
- [ ] **3. ADR Analysis** (optional): Pending → adr-*.md
- [ ] **4. Implement**: Pending → src/
- [ ] **5. Test**: Pending → ddd-03-test-report.md

## Dependencies

### Requires
- 001-core-local-data (needs Config to read interval/paths and LocalStore for safe state)

### Enables
- Unit 2 (002-booking-com-price-monitor) registers scheduled check jobs against the Scheduler hook

## Success Criteria

- [ ] All stories implemented
- [ ] Daemon starts as a local background process and runs scheduled jobs at the configured interval
- [ ] Daemon stops cleanly without corrupting local state
- [ ] Scheduler exposes a hook that downstream units can register jobs against
- [ ] Tests passing (daemon lifecycle + scheduled-trigger behavior)

## Notes

- Depends on Bolt 001 being complete (Config + LocalStore must exist).
- Daemonization approach and scheduler library are TBD — resolve during Technical Design
  and capture significant choices as ADRs.
- Keep daemon/scheduler in a separate module boundary from the data/config core
  (per `coding-standards.md`).
