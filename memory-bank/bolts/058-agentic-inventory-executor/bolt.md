---
id: 058-agentic-inventory-executor
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 004-use-provider-compatible-agentic-schemas
created: 2026-08-28T01:23:00.000Z
started: 2026-08-28T01:23:00.000Z
completed: "2026-08-28T01:45:39Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-08-28T01:24:00.000Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-28T01:25:00.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-28T01:26:00.000Z
    artifact: none-required-existing-adrs-036-037-039-040
  - name: implement
    completed: 2026-08-28T01:31:00.000Z
    artifact: source-and-regression-tests
  - name: test
    completed: 2026-08-28T01:45:39.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 053-agentic-inventory-executor
  - 056-agentic-inventory-executor
  - 057-agentic-inventory-executor
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

# Bolt: Provider-Compatible Agentic Inventory Schemas

## Objective

Repair the two live provider-schema incompatibilities that prevent Stagehand extraction and guarded
Anthropic computer use from reaching inference, without weakening BookSaver's validation or safety
boundaries.

## Stories Included

- [x] **US-158**: Use provider-compatible agentic schemas - Priority: Must

## Expected Outputs

- Stagehand-compatible typed extraction schemas without provider-compiled union parameters.
- Anthropic-compatible computer-use tool schemas with code-owned collection bounds.
- Content-free provider-schema failure diagnostics.
- Offline provider-compatibility regressions and an exact-image cookie-free smoke.

## Dependencies

- Bolts 053, 056, and 057 and ADR-036, ADR-037, ADR-039, and ADR-040 are complete and binding.

## Success Criteria

- [x] The reproduced Stagehand `18` versus `16` union-parameter rejection cannot recur.
- [x] The reproduced Anthropic unsupported `maxItems` rejection cannot recur.
- [x] Typed evidence and code-owned bounds remain fail-closed.
- [x] Focused regression, full repository, AI-DLC, and exact candidate-image provider smoke gates
  pass; Bugbot and exact merged-image deployment remain separate release gates.
