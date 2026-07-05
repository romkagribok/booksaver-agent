---
id: 007-agentic-escalation
unit: 002-agentic-escalation
intent: 002-agentic-search-monitor
type: ddd-construction-bolt
status: in-progress
stories:
  - 001-llm-agent-step-takeover
  - 002-action-guard-and-hard-caps
  - 003-trace-and-inspect-agent-runs
created: 2026-07-05T23:10:00Z
started: 2026-07-06T00:15:00Z
completed: null
current_stage: implement
stages_completed:
  - name: model
    completed: 2026-07-06T00:20:00Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-06T00:25:00Z
    artifact: ddd-02-technical-design.md
  - name: adr
    completed: 2026-07-06T00:30:00Z
    artifact: adr-015-tiered-agent-observations.md, adr-016-bounded-action-vocabulary.md, adr-017-hard-caps-now-adaptive-later.md
requires_bolts:
  - 006-search-journey-monitor
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 4
  avg_uncertainty: 5
  max_dependencies: 3
  testing_scope: 4
---

# Bolt: 007-agentic-escalation

## Overview

Second bolt of intent 002. Adds the LLM browser-agent escalation layer on top of bolt 006's journey:
per-step agent takeover with tiered observations (text/DOM first, screenshot on demand), a bounded
action vocabulary, an adapter-level action guard that keeps the agent read-only on the account, hard
configurable cost caps, and full local diagnosability (step traces, rotated failure snapshots, CLI
inspection).

## Objective

When a scripted journey step fails, the agent completes it or gives up with a coded reason — within
hard caps, never entering cancel/checkout/payment flows — and every check leaves an inspectable local
trace.

## Stories Included

- **US-020**: LLM browser agent takes over failed journey steps (Must)
- **US-021**: Enforce action guard and hard cost caps (Must)
- **US-022**: Trace and inspect agent runs locally (Should)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ⬜ **1. Domain Model**: agent-step/observation/action vocabulary, escalation trigger rules,
  budget model (steps, calls, wall-clock; screenshot turns count double), guard rules, trace records
- ⬜ **2. Technical Design**: agent loop on anthropic SDK (tool-use loop, no agent frameworks);
  browser-port extensions (element references, screenshot); denylist guard placement; trace/snapshot
  persistence + rotation; CLI command
- ⬜ **3. ADR Analysis**: tiered observations (text/DOM first, screenshot escalation);
  bounded action vocabulary vs computer-use; hard caps now / adaptive budgeting later (documented)
- ⬜ **4. Implement**
- ⬜ **5. Test**: agent loop with scripted fake LLM (deterministic action sequences); guard blocks
  mutating URLs/submissions; cap breach → `BUDGET_EXCEEDED`; trace redaction; snapshot rotation

## Dependencies

### Requires
- Bolt 006 (journey step seams, failure codes, extraction)

### Enables
- Phase-2 intent completion

## Success Criteria

- [ ] Failed scripted step → agent takeover → step success resumes journey; give-up → `AGENT_GAVE_UP`
- [ ] Guard provably blocks cancellation/checkout/payment navigation and submission (`BLOCKED_ACTION`)
- [ ] Caps configurable + validated; breach → `BUDGET_EXCEEDED`; daemon continues normally
- [ ] Docs note hard caps are the simple first version; adaptive budgeting named as future work
- [ ] `booksaver checks trace <check-id>` shows the full step trace; snapshots rotated + redacted
- [ ] Check history distinguishes scripted-only vs agent-assisted successes

## Notes

- Highest-uncertainty bolt of the intent (LLM-driven control flow). Test strategy leans on a fake
  LLM adapter emitting deterministic action sequences; live-site behavior is validated manually in
  the operations phase.
- Secrets/cookies must never appear in LLM prompts, traces, or snapshots (redaction tested).
