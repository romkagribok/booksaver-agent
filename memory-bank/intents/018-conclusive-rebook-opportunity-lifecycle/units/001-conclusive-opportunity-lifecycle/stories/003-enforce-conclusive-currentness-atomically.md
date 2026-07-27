---
id: 003-enforce-conclusive-currentness-atomically
unit: 001-conclusive-opportunity-lifecycle
intent: 018-conclusive-rebook-opportunity-lifecycle
status: complete
priority: must
created: 2026-07-27T02:32:08.000Z
assigned_bolt: 033-conclusive-opportunity-lifecycle
implemented: true
---

# Story: Enforce Conclusive Currentness Atomically

**Global story ID**: US-111

## User Story

**As a** user tapping a potentially old rebook button
**I want** every safety layer to use the same market-current rule
**So that** no conclusive update can race into a stale guided rebook.

## Acceptance Criteria

- [x] Picker, manual/callback guard, application service, and transaction agree on currentness.
- [x] A conclusive invalidation creates no session or confirmation prompt.
- [x] A technical failure does not block a still-current session.
- [x] A concurrent conclusive check cannot slip between validation and session insertion.
- [x] Rejection guidance is accurate for replacement and invalidation cases.
- [x] Ownership, active status, history, and human-action boundaries remain unchanged.

## Dependencies

US-109 and US-110.
