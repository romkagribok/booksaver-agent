---
stage: model
bolt: 057-agentic-inventory-executor
created: 2026-08-28T00:30:00Z
---

# Static Model: Agentic Cost Ledger Thread Affinity

## Entities

- **BrowserJobCostBudget**: Identifies one coordinator admission, caller, job kind, dollar limits,
  pricing table, and next attempt ordinal. It remains the sole application authority that reserves
  before a provider call and reconciles afterward.
- **CostReservation**: Persisted estimated exposure for one model attempt. It is idempotent by
  reservation identifier and remains conservative after an uncertain provider outcome.
- **ModelAttemptAudit**: Content-free persisted record of provider, model role, token usage, cost,
  latency, and terminal outcome.

## Value Objects

- **Thread-owned ledger operation**: One `reserve_call`, `reconcile_call`, or `list_attempts`
  invocation and the SQLite connection created, used, and closed by that same executing thread.
- **Execution phase**: A bounded code-owned label identifying browser launch, session application,
  attachment, navigation, semantic admission/execution, visual admission/execution, or cleanup. It
  contains no page, session, model-reasoning, or URL data.

## Aggregates

- **Job spend aggregate**: `BrowserJobCostBudget` plus its ordered reservations. Invariants:
  provider work cannot begin without a successful persistent reservation; job/day exposure cannot
  exceed existing limits; attempt ordinals remain unique and ordered; reconciliation never reopens
  allowance conservatively retained after uncertainty.

## Domain Events

- **Model attempt reserved**: Emitted logically when transactional admission succeeds before a
  provider call.
- **Model attempt reconciled**: Emitted logically when actual or conservative usage is persisted.
- **Agentic execution failed**: Content-free terminal containing execution identifier, bounded
  phase, and exception type after unexpected infrastructure failure.

## Domain Services

- **Spend admission**: Applies existing ADR-031 pricing and exposure rules through the unchanged
  `SpendLedger` contract.
- **Agentic execution**: Runs Stagehand on the dedicated async loop while consuming only admitted
  model attempts and returning typed untrusted evidence.

## Repository Interfaces

- **SpendLedger**: Existing `reserve_call`, `reconcile_call`, and `list_attempts` contract is
  unchanged. Its SQLite implementation must be callable from either coordinator or async browser
  threads without transferring a live connection between them.

## Ubiquitous Language

- **Connection ownership**: The thread that creates a SQLite connection is the only thread that
  uses and closes it.
- **Persistent admission**: Transactional reservation of estimated provider exposure before the
  external call begins.
- **Thread-affinity failure**: `sqlite3.ProgrammingError` caused by using a connection from a thread
  other than its creator.
- **Fail closed**: Return a typed provider failure and spend nothing when admission cannot be
  persisted safely.

## Story Coverage

- US-157 is covered by the job-spend invariants, unchanged `SpendLedger` contract, thread-owned
  operation value object, and content-free failure event.
