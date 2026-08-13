---
unit: 001-adaptive-model-policy
intent: 022-adaptive-booking-browser-resilience
phase: inception
status: complete
created: 2026-08-13T01:59:59.000Z
updated: 2026-08-13T01:59:59.000Z
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: Adaptive Model Policy

## Purpose

Choose the least costly approved model that can complete guarded browser recovery, replace Sonnet 5
with Opus 5 after objective quality failure, and enforce caller-safe job and deployment dollar
limits before provider work starts.

## Scope

### In Scope

- Validated Sonnet 5 primary and Opus 5 escalation profiles.
- Typed escalation triggers and bounded handoff context.
- Conservative per-call cost admission and actual/conservative usage charging.
- Persisted UTC deployment-day spend plus existing caller-scoped accounting.
- Sanitized offline/live replay comparison and production qualification gates.

### Out of Scope

- Browser step registration and deterministic verification, owned by Unit 2.
- DOM-drift incidents, owner notification, and diagnostic bundles, owned by Unit 3.
- Fable models, a second provider, arbitrary model strings, or cross-user key fallback.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-5 | Escalate Sonnet 5 to Opus 5 on measured quality failure | Must |
| FR-6 | Enforce job and deployment dollar ceilings | Must |
| FR-7 | Qualify and monitor model recovery quality | Must |

## Domain Concepts

- **ModelProfile**: Validated provider/model/role/prompt/pricing combination.
- **EscalationTrigger**: Typed runtime evidence that Sonnet is ineffective but Opus remains eligible.
- **ModelAttempt**: One bounded provider call with role, usage, latency, and outcome metadata.
- **CostReservation**: Conservative USD estimate admitted before a call.
- **DeploymentSpendLedger**: Restart-safe UTC-day accounting shared by all browser jobs.
- **QualificationReport**: Sanitized correctness, safety, latency, usage, cost, and routing results.

## Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| Select model | Choose primary or escalation profile from policy and history | Role, attempts, terminal/safety state | Model profile or typed stop |
| Admit call | Reserve conservative provider cost | Job/day ledgers, bounded tokens, profile | Admission or exact cost reason |
| Charge usage | Reconcile actual or conservative provider usage once | Provider response/error, reservation | Persisted caller/job/day audit |
| Qualify profiles | Replay sanitized failure fixtures | Profile pair, fixture set, run count | Qualification report and gate result |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 3 |
| Must Have | 3 |
| Should Have | 0 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-130 | Escalate Sonnet to Opus on quality failure | Must | Planned |
| US-131 | Enforce browser-job and daily dollar ceilings | Must | Planned |
| US-132 | Qualify adaptive model profiles | Must | Planned |

## Dependencies

### Depends On

- Existing `AgentBrain`, Anthropic adapters, provider client factory, caller-scoped keys, LLM usage
  counters, recovery policy, configuration, replay runner, and SQLite store.

### Depended By

- `002-dom-resilient-browser-workflows` uses the router and job budget for all recovery,
  interpretation, and final diagnosis.
- `003-dom-drift-incident-operations` records attempted profiles and cost/provider stop state.

### External Dependencies

- **Anthropic API**: Sonnet 5 and Opus 5 model availability and usage reporting - Risk: High.

## Technical Context

- Add provider-neutral routing/admission ports; keep Anthropic SDK details in infrastructure.
- Version the conservative model-price table and reject unpriced/unapproved model profiles.
- Persist deployment spend transactionally by UTC day; preserve personal-key attribution.
- Reuse structured outcome history without copying provider reasoning between models.

## Constraints

- Sonnet 5 and Opus 5 only; Fable is rejected for this policy.
- USD 1 estimated maximum per browser job and USD 10 per deployment UTC day.
- Existing call/check/user limits remain independent outer boundaries.
- A safety terminal state cannot be overridden by escalation.

## Success Criteria

### Functional

- [ ] Eligible Sonnet quality failures select Opus exactly as specified.
- [ ] Ineligible safety/provider/budget states terminate without wasteful escalation.
- [ ] No admitted call can conservatively exceed the remaining job/day dollar ceiling.
- [ ] Spend survives restart and remains attributable without cross-user key fallback.
- [ ] Replay reports enforce correctness and zero-prohibited-action gates.

### Non-Functional

- [ ] Healthy deterministic browser work incurs zero model cost.
- [ ] Routing, cost, and replay tests are deterministic offline.
- [ ] Provider/model/usage audit contains no secret or page content.

## Bolt Suggestions

- `041-adaptive-model-policy`: one DDD bolt for US-130 through US-132.
