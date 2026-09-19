---
id: 003-qualify-trusted-reconciliation
unit: 012-trusted-inventory-reconciliation
intent: 023-replaceable-agentic-browser-executor
status: in-progress
priority: must
created: 2026-09-19T22:04:01Z
assigned_bolt: 077-trusted-inventory-reconciliation
implemented: false
---

# US-194: Qualify trusted reconciliation for the affected caller

As a user, I want the corrected list verified against my account without risking other users or my booking history.

## Acceptance criteria

- Deterministic tests cover complete nonempty and empty scopes, missing/delayed groups, duplicates,
  root/direct reservations, unknown items, mixed non-hotels, truncated evidence and root/group churn.
- Cover wrong caller/run/session proof, forged model completeness, cancellation/rebooking identity,
  complete-then-incomplete refresh, transaction rollback and unaffected other callers/history.
- Exercise reader → validator → reconciliation → active/monitoring/Telegram projections. Prove retired
  rows no longer qualify and incomplete unseen rows stay preserved and clearly unverified.
- Run the full relevant test/Ruff/mypy and AI-DLC gates; capture actual affected-caller normal-flow
  isolated replay with notifications disabled and production source/state protected.
- Record outcomes and limitations in the test report, then run the official completion cascade.

## Mandatory Operations release exit criteria

- Successful final-head Cursor Bugbot, resolved threads and passing merge gate.
- Exact built image passes installed-source/dependency/CLI Development checks and affected-caller
  isolated Staging, including accepted complete/partial classification and no false retirement.
- Preserve restricted backup and verified rollback image; promote only the qualified image and verify
  process, logs, health/heartbeat, dependencies, SQLite/FKs, ports and browser cleanup.
- Record production inventory acceptance separately from cloned price replay/native Telegram testing.
