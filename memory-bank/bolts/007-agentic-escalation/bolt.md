---
id: 007-agentic-escalation
unit: 002-agentic-escalation
intent: 002-agentic-search-monitor
type: ddd-construction-bolt
status: complete
stories:
  - 001-llm-agent-step-takeover
  - 002-action-guard-and-hard-caps
  - 003-trace-and-inspect-agent-runs
created: 2026-07-05T23:10:00.000Z
started: 2026-07-06T00:15:00.000Z
completed: "2026-07-06T12:45:43Z"
current_stage: null
stages_completed:
  - name: model
    completed: 2026-07-06T00:20:00.000Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-06T00:25:00.000Z
    artifact: ddd-02-technical-design.md
  - name: adr
    completed: 2026-07-06T00:30:00.000Z
    artifact: adr-015-tiered-agent-observations.md, adr-016-bounded-action-vocabulary.md, adr-017-hard-caps-now-adaptive-later.md
  - name: implement
    completed: 2026-07-06T01:10:00.000Z
    artifact: domain/agent.py + monitor/{browser_agent,trace}.py + journey escalation seams + AnthropicAgentBrain + Playwright observe/act/screenshot + schema v6 + checks CLI
  - name: test
    completed: 2026-07-06T01:20:00.000Z
    artifact: ddd-03-test-report.md
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

- ✅ **1. Domain Model**: Complete → ddd-01-domain-model.md
- ✅ **2. Technical Design**: Complete → ddd-02-technical-design.md
- ✅ **3. ADR Analysis**: Complete → adr-015, adr-016, adr-017
- ✅ **4. Implement**: Complete → agent loop + guard + caps + traces + CLI
- ✅ **5. Test**: Complete → ddd-03-test-report.md (345/345; 68 new)

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
