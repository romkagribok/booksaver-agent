---
id: 019-on-demand-check-orchestration
unit: 001-on-demand-check-orchestration
intent: 007-telegram-on-demand-checks
type: simple-construction-bolt
status: complete
stories:
  - 001-discover-and-select-immediate-check
  - 002-run-responsive-background-check
  - 003-serialize-all-check-work
  - 004-share-daily-check-and-llm-budgets
  - 005-reuse-normal-monitoring-pipeline
created: 2026-07-18T23:40:00Z
started: 2026-07-18T23:40:00Z
completed: "2026-07-18T23:57:35Z"
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-18T23:40:00Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-18T23:48:00Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-18T23:55:00Z
    artifact: test-walkthrough.md
requires_bolts:
  - 007-agentic-escalation
  - 010-conversational-booking-ops
  - 016-interactive-command-navigation
  - 017-conversational-booking-management
enables_bolts: []
requires_units:
  - 002-agentic-escalation
  - 003-conversational-booking-ops
  - 001-interactive-command-navigation
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 4
  testing_scope: 3
---

# Bolt: On-Demand Check Orchestration

## Objective

Deliver `/checknow` and refactor the daemon so scheduled and immediate checks share one serialized,
budget-aware, fully instrumented monitoring pipeline.

## Stories Included

- [x] US-052: Discover and select an immediate check - implemented, awaiting closure.
- [x] US-053: Run a responsive background check - implemented, awaiting closure.
- [x] US-054: Serialize all check work - implemented, awaiting closure.
- [x] US-055: Share daily check and LLM budgets - implemented, awaiting closure.
- [x] US-056: Reuse the normal monitoring pipeline - implemented, awaiting closure.

## Expected Outputs

- Shared check coordinator and scheduler/daemon wiring.
- Thread-safe correct daily counters and actual LLM usage reporting.
- `/checknow` catalog, picker, typed selector, callback, worker, and result formatting.
- Comprehensive coordinator, limit, gateway, and regression tests.
- Simple-bolt Plan, Implement, and Test walkthroughs.

## Success Criteria

- [x] One browser/check execution exists at a time and duplicate requests never queue.
- [x] Both paths share exact limits, traces, persistence, savings, and notification behavior.
- [x] Telegram remains responsive and shutdown-safe.
- [x] All scoped quality, regression, diff, and AI-DLC checks pass.

## Execution Note

Continuous progression through the final Test checkpoint was authorized. The product owner approved
final validation, and the official completion script closed the bolt on 2026-07-18T23:57:35Z.
