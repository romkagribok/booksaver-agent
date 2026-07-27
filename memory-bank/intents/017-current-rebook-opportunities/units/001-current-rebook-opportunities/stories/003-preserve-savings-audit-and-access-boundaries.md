---
id: 003-preserve-savings-audit-and-access-boundaries
unit: 001-current-rebook-opportunities
intent: 017-current-rebook-opportunities
status: complete
priority: must
created: 2026-07-27T02:10:44.000Z
assigned_bolt: 032-current-rebook-opportunities
implemented: true
---

# Story: Preserve Savings Audit and Access Boundaries

**Global story ID**: US-108

## User Story

**As the** BookSaver operator
**I want** current action choices without deleting historical evidence or weakening scoping
**So that** the correction remains explainable and safe.

## Acceptance Criteria

- [x] Historical savings rows remain queryable by existing history readers.
- [x] Current-choice queries include only active bookings owned by the requester.
- [x] Foreign IDs retain the existing non-enumerating response.
- [x] Confirmation, session concurrency, post-rebook propagation, and human final clicks are
      unchanged.
- [x] No schema migration, cleanup task, dependency, or new external request is introduced.

## Dependencies

US-106 and US-107.
