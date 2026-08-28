---
id: 003-keep-agentic-cost-ledger-thread-affine
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-08-28T00:28:18Z
assigned_bolt: 057-agentic-inventory-executor
implemented: true
---

# Story: Keep Agentic Cost Accounting Thread-Affine

## User Story

**As a** BookSaver deployment owner
**I want** Stagehand model admission and reconciliation to use SQLite only from connections owned by
the executing thread
**So that** agentic inventory and price execution can reach semantic perception while preserving
restart-safe hard cost limits

## Acceptance Criteria

- [x] Agentic semantic and computer-use admission, reconciliation, and attempt lookup never reuse a
  SQLite connection created on the coordinator thread from the async browser thread.
- [x] The production fix does not disable SQLite's default thread-affinity check and does not share a
  mutable connection concurrently across threads.
- [x] Existing transactional `$1/job`, `$10/deployment-day`, caller attribution, idempotency, and
  daily-call limits remain exact for both inventory and price executors.
- [x] A regression test drives a real SQLite-backed cost budget through `AsyncLoopRunner` and proves
  admission, reconciliation, and persisted audit lookup succeed across the production thread boundary.
- [x] Provider calls remain blocked until persistent admission succeeds, and failures retain a
  content-free execution phase and exception type in local logs.
- [x] Existing Stagehand, inventory safety, persistence, and coordinator tests remain green.

## Dependencies

- US-153, US-156; ADR-031, ADR-036, ADR-037, and ADR-039.

## Out of Scope

- Relaxing cost caps, changing model routing, disabling SQLite thread checks, changing browser
  authority, or altering positive-only inventory reconciliation.
