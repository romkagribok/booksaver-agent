---
stage: plan
bolt: 019-on-demand-check-orchestration
created: 2026-07-18T23:40:00Z
---

# Implementation Plan: On-Demand Check Orchestration

## Objective

Add a safe immediate Telegram check while removing the split-brain risk between scheduler-owned and
Telegram-owned browser orchestration.

## Technical Approach

1. Make `DailyCounter` synchronized and quota-aware; fix fair scheduling to honor remaining quota.
2. Extend the monitor with per-run LLM cap injection and observable actual call use without changing
   its never-raise result contract.
3. Extract the CLI check closure into a daemon-lifetime `CheckCoordinator` that non-blockingly owns a
   global execution gate, counters, browser/store lifecycle, monitoring, savings, and notices.
4. Give the scheduler and Telegram gateway the same coordinator. The gateway registers `/checknow`,
   caller-scoped selection, callbacks, daemon background workers, worker-time reauthorization, and
   concise completion/failure sends.
5. Test concurrency, quotas, LLM depletion, scoping, reauthorization, responsiveness, shutdown, and
   full normal-pipeline reuse before running all project validators.

## Acceptance Criteria

- [ ] US-052–US-056 acceptance criteria pass.
- [ ] No duplicated orchestration or second browser/scheduler exists.
- [ ] Existing scheduler and Telegram behavior remains compatible.
- [ ] Ruff, mypy, focused/full tests, diff checks, and AI-DLC validators pass.
