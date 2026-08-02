---
id: 038-shared-booking-browser-recovery
unit: 001-shared-booking-browser-recovery
intent: 021-booking-browser-llm-recovery
type: ddd-construction-bolt
status: complete
stories:
  - 001-detect-and-stop-semantic-no-progress
  - 002-reorient-with-evidence-rich-feedback
  - 003-back-every-booking-browser-step-with-guarded-recovery
  - 004-evaluate-recovery-with-replay-fixtures
created: 2026-08-02T18:07:49Z
started: 2026-08-02T18:16:29Z
completed: "2026-08-02T18:41:16Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-08-02T18:16:29Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-02T18:18:46Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-02T18:18:46Z
    artifact: adr-030-shared-progress-aware-booking-browser-recovery.md
  - name: implement
    completed: 2026-08-02T18:40:18Z
  - name: test
    completed: 2026-08-02T18:41:16Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 007-agentic-escalation
  - 013-production-reliability
  - 014-production-reliability
  - 015-production-reliability
enables_bolts:
  - 039-agent-assisted-booking-inventory
requires_units: []
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 038-shared-booking-browser-recovery

## Overview

Replace ref-based, free-form browser recovery with a provider-neutral, progress-aware controller
that receives structured outcomes, detects semantic no-progress, reorients with visual evidence,
and stops accurately within a tighter step-local policy.

## Objective

Deliver reusable domain/application/browser/provider contracts, preserve guarded price-search
recovery, add caller/operation LLM resolution, and establish sanitized offline/live replay tests.

## Stories Included

- **US-122**: Detect and stop semantic no-progress (Must)
- **US-123**: Reorient with evidence-rich feedback (Must)
- **US-124**: Back every booking browser step with guarded recovery (Must)
- **US-125**: Evaluate recovery with replay fixtures (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. ADR Analysis**: Complete → ADR-030
- [x] **4. Implement**: Complete → shared recovery source and docs
- [x] **5. Test**: Complete → `ddd-03-test-report.md`

## Dependencies

### Requires

- Existing agentic escalation and production search reliability bolts 007 and 013–015.
- Existing coordinator, usage accounting, caller-scoped LLM factory, traces, and guards.

### Enables

- `039-agent-assisted-booking-inventory`.

## Success Criteria

- [x] Structured outcomes distinguish execution from verified progress.
- [x] Changed refs and alternating equivalent targets cannot evade loop bounds.
- [x] Evidence-rich reorientation and four-call/60-second limits are enforced.
- [x] Existing price-search recovery and safety behavior remain correct.
- [x] Sanitized replay fixtures and provider-neutral evaluation are available.
- [x] Focused and full repository checks pass.

## Notes

The product owner authorized continuous AI-DLC progression through implementation and tests. Stage
checkpoints remain documented; commit, push, PR, merge, deployment, and production model execution
remain outside this bolt's authorization.
