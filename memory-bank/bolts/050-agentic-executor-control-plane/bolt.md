---
id: 050-agentic-executor-control-plane
unit: 001-agentic-executor-control-plane
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 001-define-executor-evidence-contract
  - 002-validate-every-observation-independently
  - 003-lease-transient-owner-sessions-safely
  - 004-route-and-account-for-bounded-execution
created: '2026-08-16T19:18:41Z'
started: '2026-08-16T19:23:47Z'
completed: '2026-08-17T03:24:03Z'
current_stage: null
stages_completed:
  - name: domain-model
    completed: '2026-08-17T03:15:08Z'
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: '2026-08-17T03:16:20Z'
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: '2026-08-17T03:16:20Z'
    artifact: adr-036-trusted-control-plane-and-executor-port.md
  - name: implement
    completed: '2026-08-17T03:22:39Z'
    artifact: source-and-tests
  - name: test
    completed: '2026-08-17T03:23:22Z'
    artifact: ddd-03-test-report.md
requires_bolts: []
enables_bolts:
  - 051-local-agentic-price-executor
requires_units: []
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: 050-agentic-executor-control-plane

## Objective

Introduce provider-neutral contracts, session leases, independent validation, exact limits, fake
execution, and routing policy without changing production price-check routing.

## Stories Included

- US-143 through US-146 (Must).

## Stages

- [x] Domain model: executor/evidence/lease/routing types.
- [x] Technical design: integration seams and migration boundary.
- [x] ADR analysis: ADR-036.
- [x] Implement: contracts, services, fake, config/routing with legacy default.
- [x] Test: contract, fail-closed validation, secret absence, and accounting.

## Dependencies

- Existing model policy, user/session services, coordinator, offer selection, and legacy monitor.

## Success Criteria

- [ ] Provider-neutral tests pass and production behavior remains legacy by default.
- [ ] No untrusted observation bypasses BookSaver validation.
- [ ] Exact budgets and owner-only canary admission are enforced.
