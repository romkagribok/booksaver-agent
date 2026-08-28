---
stage: test
bolt: 057-agentic-inventory-executor
created: 2026-08-28T00:32:53Z
---

# Test Report: Agentic Cost Ledger Thread Affinity

## Summary

- **Focused regression**: 135 passed across model-policy persistence, inventory executor, price
  executor, and coordinator tests.
- **Full repository**: 1788 passed with 55 existing deprecation warnings.
- **Static checks**: Ruff clean; mypy clean across 127 source files.
- **AI-DLC checks**: artifact validation and status integrity both report zero issues across 57
  bolts and 23 intents.
- **Diff hygiene**: `git diff --check` clean.

## Acceptance Criteria Validation

- ✅ **US-157 / thread ownership**: `ThreadScopedSqliteSpendLedger` retains only a path and creates,
  uses, and closes one `SqliteStore` inside each operation.
- ✅ **US-157 / SQLite safety**: no `check_same_thread=False` or shared connection was introduced.
- ✅ **US-157 / exact accounting**: the adapter delegates to the existing transactional
  `SqliteSpendLedger`; job/day caps, idempotency, caller checks, and conservative reconciliation are
  unchanged.
- ✅ **US-157 / production topology**: a real SQLite-backed `BrowserJobCostBudget` reserves,
  reconciles, and reads its persisted audit through `AsyncLoopRunner`.
- ✅ **US-157 / fail closed and diagnostics**: provider work remains after admission, while an
  injected `sqlite3.ProgrammingError` returns provider failure and logs only operation, model role,
  prompt version, and exception type.
- ✅ **US-157 / capability coverage**: the shared agentic budget factory supplies the corrected
  adapter to both inventory and price executors.

## Issues Found

- The first logging assertion expected semantic observation admission, while the traversal starts
  with typed scope extraction. The regression was corrected to the observed code-owned extraction
  phase; no production behavior changed.

## Remaining Release Gates

- Cursor Bugbot must pass on the final pushed head before merge.
- The exact merged Docker image must pass staging clone, Stagehand/Chromium, health, database,
  Telegram, and live owner acceptance checks before the release is considered operationally proven.
