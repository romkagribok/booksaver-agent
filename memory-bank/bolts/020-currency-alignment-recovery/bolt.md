---
id: 020-currency-alignment-recovery
unit: 001-currency-alignment-recovery
intent: 008-currency-aligned-price-checks
type: simple-construction-bolt
status: planned
stories:
  - 001-propagate-baseline-currency
  - 002-verify-rendered-currency
  - 003-recover-currency-once
  - 004-report-unresolved-currency
  - 005-preserve-shared-check-pipeline
created: 2026-07-19T00:32:13Z
started: null
completed: null
current_stage: null
stages_completed: []
requires_bolts:
  - 006-search-journey-monitor
  - 007-agentic-escalation
  - 015-production-reliability
  - 019-on-demand-check-orchestration
enables_bolts: []
requires_units:
  - 001-search-journey-monitor
  - 002-agentic-escalation
  - 001-on-demand-check-orchestration
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: Currency Alignment Recovery

## Overview

Correct VPS-localized currency mismatches by carrying the baseline currency as trusted navigation
context, verifying rendered offer currencies, attempting one bounded deterministic/guarded-agent
alignment, and reporting unresolved mismatches without cross-currency arithmetic.

## Objective

Deliver all five currency-alignment stories through the existing search monitor and shared check
pipeline, with actionable traces/Telegram results and no relaxation of safety or equivalence gates.

## Stories Included

- [ ] **US-057**: Propagate baseline currency through trusted navigation - Must.
- [ ] **US-058**: Verify rendered candidate currencies - Must.
- [ ] **US-059**: Recover an otherwise-valid mismatch once - Must.
- [ ] **US-060**: Report unresolved currency alignment safely - Must.
- [ ] **US-061**: Preserve the shared check pipeline and safety gates - Must.

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

## Stages

- [ ] **1. Plan**: Pending → `implementation-plan.md`
- [ ] **2. Implement**: Pending → source/tests + `implementation-walkthrough.md`
- [ ] **3. Test**: Pending → `test-walkthrough.md`

## Expected Outputs

- Trusted currency URL/preference helper and protected search/property query propagation.
- Currency-only selection evidence and one bounded recovery integration.
- Guarded visible-selector fallback using existing budgets when deterministic alignment is unverified.
- Currency-specific check failure, trace/log evidence, and Telegram result detail.
- Focused regression tests and complete static/automated verification records.

## Dependencies

### Requires

- Bolt 006 search journey and offer extraction.
- Bolt 007 guarded agent, budgets, action guard, and traces.
- Bolt 015 semantic property/rate readiness.
- Bolt 019 shared scheduled/on-demand orchestration.

### Enables

- VPS validation against the Home2 Suites currency-mismatch reproduction.

## Success Criteria

- [ ] All five stories and acceptance criteria are implemented.
- [ ] No unlike-currency amounts are compared or notified as savings.
- [ ] Recovery is deterministic-first, agent-optional, verified, and limited to one cycle.
- [ ] Existing check and safety behavior remains compatible.
- [ ] Focused tests, full pytest, Ruff, and mypy pass.
- [ ] Code and AI-DLC artifacts receive human review before commit/push.

## Notes

No ADR is planned: this applies the already-approved same-currency domain invariant and existing
scripted-first/guarded-agent architecture without a new technology or architectural pattern.
