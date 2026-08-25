---
id: 054-local-agentic-price-executor
unit: 002-local-agentic-price-executor
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: in-progress
stories:
  - 005-launch-stagehand-in-docker-runtime
created: 2026-08-25T01:10:13Z
started: 2026-08-25T01:10:13Z
completed: null
current_stage: test
stages_completed:
  - name: domain-model
    completed: 2026-08-25T01:12:00Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-25T01:13:00Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-25T01:13:00Z
    artifact: adr-037-amendment
  - name: implement
    completed: 2026-08-25T01:16:00Z
    artifact: source-and-tests
requires_bolts:
  - 051-local-agentic-price-executor
enables_bolts:
  - 052-agentic-browser-qualification
requires_units:
  - 001-agentic-executor-control-plane
blocks: false
complexity:
  avg_complexity: 1
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 054-local-agentic-price-executor

## Objective

Correct the Stagehand launch contract for BookSaver's existing non-root Docker runtime and prove the
exact production image can attach and tear down without a CI environment workaround.

## Stories Included

- US-155 (Must).

## Stages

- [x] Domain model: container browser launch policy and preserved security boundaries.
- [x] Technical design: explicit Stagehand launch setting and regression seams.
- [x] ADR analysis: confirm ADR-037 already governs the packaging decision.
- [x] Implement: pass the explicit setting and correct deployment documentation.
- [ ] Test: focused regression, full quality gate, and production-image Stagehand smoke.

## Dependencies

- Bolt 051 and the current Docker/Playwright packaging baseline.

## Success Criteria

- [ ] Stagehand starts without `CI` inside the exact Docker image.
- [ ] Browser processes remain unprivileged and transient.
- [ ] No browser authority, egress, session, routing, or qualification boundary changes.
