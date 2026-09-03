---
id: 064-browser-use-price-executor
unit: 006-browser-use-price-executor
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 001-default-price-checks-to-browser-use
  - 002-execute-guarded-browser-use-price-episode
  - 003-diagnose-model-visible-price-page
  - 004-preserve-rollback-and-qualify-browser-use
  - 005-replay-deployed-browser-use-price-path
  - 006-remove-stagehand-inventory-price-prerequisite
created: 2026-09-02T23:44:45Z
started: 2026-09-02T23:50:00Z
completed: 2026-09-03T01:41:00Z
current_stage: complete
stages_completed:
  - name: domain-model
    completed: 2026-09-02T23:52:00Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-09-02T23:56:00Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-09-03T00:00:00Z
    artifact: adr-043-browser-use-default-price-executor.md
  - name: implement
    completed: 2026-09-03T00:14:45Z
    artifact: src/booksaver/infrastructure/browser/browser_use_price_executor.py
  - name: test
    completed: 2026-09-03T01:41:00Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 050-agentic-executor-control-plane
  - 051-local-agentic-price-executor
  - 054-local-agentic-price-executor
  - 060-agentic-inventory-executor
  - 063-agentic-inventory-executor
enables_bolts:
  - 055-legacy-price-selector-retirement
requires_units:
  - 001-agentic-executor-control-plane
  - 002-local-agentic-price-executor
  - 004-agentic-inventory-executor
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: Browser Use Default Price Execution

## Objective

Implement and prove local Browser Use as BookSaver's default price executor for both `/checknow` and
scheduled work while retaining BookSaver validation, explicit rollback, isolated qualification,
privacy-safe diagnostics, and production-equivalent replay.

## Stories Included

- [x] **US-164**: Default manual and scheduled price checks to Browser Use - Priority: Must
- [x] **US-165**: Execute a guarded typed Browser Use price episode - Priority: Must
- [x] **US-166**: Diagnose the model-visible price page before paid inference - Priority: Must
- [x] **US-167**: Preserve explicit rollback and qualify Browser Use independently - Priority: Must
- [x] **US-168**: Replay the deployed Browser Use price path without Telegram - Priority: Must
- [x] **US-169**: Remove the Stagehand inventory prerequisite from price operations - Priority: Must

## Expected Outputs

- Browser Use price adapter and explicit executor-selection configuration.
- Shared manual/scheduled wiring through `PriceBrowserExecutor`.
- Guarded actions, typed observation mapping, model-view preflight, and redacted diagnostics.
- Browser Use-specific qualification policy and regression coverage.
- Operator-only isolated price replay and exact-container production verification.
- Browser Use composition for every agentic inventory prerequisite in the price flow.

## Dependencies

- Units 001, 002, and 004 are complete; Unit 003's live gate remains independent.
- Bolts 050, 051, 054, 060, and 063 are complete.
- Existing Anthropic key, pinned Browser Use runtime, Chromium image, and owner session are available.

## Success Criteria

- [x] Both price triggers resolve Browser Use by default and preserve existing BookSaver policy.
- [x] No same-job browser-harness fallback or selector dependency is introduced.
- [x] Safety, privacy, cost, deadline, teardown, and typed-evidence tests pass.
- [x] Stagehand and deterministic rollback remain explicit and tested.
- [x] The exact candidate-image VPS replay returns one BookSaver-accepted price observation.
