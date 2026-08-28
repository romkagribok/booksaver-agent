---
id: 057-agentic-inventory-executor
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 003-keep-agentic-cost-ledger-thread-affine
created: 2026-08-28T00:28:18Z
started: 2026-08-28T00:28:18Z
completed: 2026-08-28T00:32:53Z
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-08-28T00:30:00Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-28T00:31:00Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-28T00:31:00Z
    artifact: none-required-existing-adrs-031-036-037-039
  - name: implement
    completed: 2026-08-28T00:31:50Z
    artifact: source-and-regression-tests
  - name: test
    completed: 2026-08-28T00:32:53Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 053-agentic-inventory-executor
  - 056-agentic-inventory-executor
enables_bolts: []
requires_units:
  - 001-agentic-executor-control-plane
  - 002-local-agentic-price-executor
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: Agentic Cost Ledger Thread Affinity

## Objective

Repair the production thread boundary between the dedicated async Stagehand runner and BookSaver's
persistent model-cost ledger without weakening SQLite safety or any cost limit.

## Stories Included

- [x] **US-157**: Keep agentic cost accounting thread-affine - Priority: Must

## Expected Outputs

- Thread-owned SQLite spend-ledger operations for agentic execution.
- Cross-thread real-SQLite regression coverage for reservation, reconciliation, and audit lookup.
- Content-free phase diagnostics for unexpected agentic inventory failures.
- No change to provider, browser, session, action, reconciliation, or cost authority.

## Dependencies

- Bolts 053 and 056 and ADR-031, ADR-036, ADR-037, and ADR-039 are complete and binding.

## Success Criteria

- [x] The reproduced `sqlite3.ProgrammingError` cannot occur at first semantic model admission.
- [x] Persistent cost admission remains transactional and fail-closed before provider calls.
- [x] Both agentic inventory and price budgets use the corrected persistence boundary.
- [x] Focused regression, full repository, and AI-DLC construction gates pass; Bugbot and exact-image
  deployment remain separate release gates.
