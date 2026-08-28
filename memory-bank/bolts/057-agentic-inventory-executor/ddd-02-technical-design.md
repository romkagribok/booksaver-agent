---
stage: design
bolt: 057-agentic-inventory-executor
created: 2026-08-28T00:31:00Z
---

# Technical Design: Agentic Cost Ledger Thread Affinity

## Architecture Pattern

Keep the existing synchronous coordinator, dedicated async Stagehand runner, application
`BrowserJobCostBudget`, and `SpendLedger` port. Add an infrastructure ledger adapter that stores
only the database path and opens a short-lived `SqliteStore` inside each ledger operation. The
connection is therefore created, used, committed/rolled back, and closed on the calling thread.

This is an adapter correction under ADR-031 and ADR-037, not a new domain or technology decision.

## Layer Structure

- **Domain**: No changes. Cost, evidence, session, and safety types remain authoritative.
- **Application**: `BrowserJobCostBudget` and `SpendLedger` contracts remain unchanged.
- **Infrastructure persistence**: Add `ThreadScopedSqliteSpendLedger`, delegating each operation to
  the existing transactional `SqliteSpendLedger` through a fresh thread-owned `SqliteStore`.
- **Coordinator**: Use the thread-scoped adapter only for agentic budgets that cross into
  `AsyncLoopRunner`; keep same-thread legacy/adaptive paths unchanged.
- **Browser adapter**: Track a bounded execution phase and include it with the exception type in
  unexpected-failure logs; never include exception messages or provider/page/session content.

## API Design

- No public CLI, Telegram, executor-port, or provider API changes.
- New infrastructure constructor: `ThreadScopedSqliteSpendLedger(db_path: Path)`.
- Existing methods: `reserve_call(request)`, `reconcile_call(request)`, and
  `list_attempts(job_id)`.

## Data Model

- No schema or migration changes.
- Existing `llm_cost_reservations` and `llm_spend_days` transactions remain owned by
  `SqliteSpendLedger`.
- Connection lifetime changes only: one operation, one calling-thread-owned connection.

## Security Design

- Keep SQLite `check_same_thread=True` and never share a connection between threads.
- Provider calls remain after successful reservation only.
- Preserve integer-microdollar accounting, transactional `BEGIN IMMEDIATE`, idempotent reservation,
  caller authorization, and conservative reconciliation.
- Log only execution identifier, code-owned phase, and exception class.

## NFR Implementation

- **Reliability**: Real-SQLite cross-thread regression reproduces the production topology.
- **Concurrency**: Existing SQLite transactions serialize short ledger writes; the coordinator's
  global browser gate still prevents overlapping agentic jobs.
- **Performance**: A few local connection opens per model turn are negligible beside browser/model
  latency and avoid long-lived cross-thread state.
- **Maintainability**: Reuse the existing ledger implementation rather than duplicate cost rules.

## Verification Plan

1. Prove a normal `SqliteStore` still raises across `AsyncLoopRunner` in the diagnostic model.
2. Prove the new adapter reserves, reconciles, and lists a real attempt from that runner.
3. Prove coordinator agentic budget construction selects the new adapter while legacy paths retain
   their existing ledger.
4. Run persistence, model-policy, price executor, inventory executor, coordinator, lint, typing,
   full tests, AI-DLC validation, Docker smoke, Bugbot, and staged production verification.
