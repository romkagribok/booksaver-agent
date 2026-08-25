---
id: 051-local-agentic-price-executor
unit: 002-local-agentic-price-executor
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 001-run-stagehand-in-transient-local-browser
  - 002-guard-semantic-navigation-and-extract-rates
  - 003-recover-visually-through-guarded-computer-use
  - 004-confine-content-and-disclose-processing
created: '2026-08-16T19:18:41Z'
started: '2026-08-17T03:24:11Z'
completed: '2026-08-17T04:18:32Z'
current_stage: null
stages_completed:
  - name: domain-model
    completed: '2026-08-17T03:26:41Z'
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: '2026-08-17T03:26:41Z'
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: '2026-08-17T03:26:41Z'
    artifact: adr-037-local-stagehand-and-guarded-computer-use.md
  - name: implement
    completed: '2026-08-17T04:17:00Z'
    artifact: source-and-tests
  - name: test
    completed: '2026-08-17T04:18:00Z'
    artifact: ddd-03-test-report.md
requires_bolts:
  - 050-agentic-executor-control-plane
enables_bolts:
  - 052-agentic-browser-qualification
  - 054-local-agentic-price-executor
requires_units:
  - 001-agentic-executor-control-plane
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 3
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 051-local-agentic-price-executor

## Objective

Implement complete semantic price navigation/perception with one guarded visual fallback on the same
transient local browser, then wire opt-in routing while keeping legacy as default.

## Stories Included

- US-147 through US-150 (Must).

## Stages

- [x] Domain model: action previews, visual actions, and terminal mapping.
- [x] Technical design: Stagehand runner, CDP custody, telemetry, and Anthropic loop.
- [x] ADR analysis: ADR-037.
- [x] Implement: adapter, fallback, routing, disclosure, and cleanup.
- [x] Test: adapter fixtures, guards, same-browser handoff, secrets, and packaging.

## Dependencies

- Bolt 050.

## Success Criteria

- [x] No BookSaver-owned Booking selectors appear in the agentic price path.
- [x] All semantic and visual actions are code-guarded.
- [x] Legacy remains the default route.
