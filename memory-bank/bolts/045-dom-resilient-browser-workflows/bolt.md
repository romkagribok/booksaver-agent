---
id: 045-dom-resilient-browser-workflows
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
type: ddd-construction-bolt
status: complete
stories:
  - 002-classify-current-page-with-llm-fallback
  - 003-recover-and-interpret-safe-dom-drift
  - 004-explain-every-terminal-browser-outcome
created: 2026-08-14T02:03:30.000Z
started: 2026-08-14T02:03:30.000Z
completed: "2026-08-14T02:24:21Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-08-14T02:07:00.000Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-14T02:12:00.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-14T02:12:00.000Z
    artifact: none-required-existing-adrs-032-033-034
  - name: implement
    completed: 2026-08-14T02:20:00.000Z
    artifact: source-code
  - name: test
    completed: 2026-08-14T02:24:00.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 042-dom-resilient-browser-workflows
  - 043-dom-resilient-browser-workflows
  - 044-dom-drift-incident-operations
enables_bolts: []
requires_units:
  - 001-adaptive-model-policy
  - 003-dom-drift-incident-operations
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 045-dom-resilient-browser-workflows

## Overview

Correct the production `/connect` loop where a changed Booking.com mobile inventory DOM causes the
fixed authentication probe to reload forever before adaptive classification or incident reporting.

## Objective

Make remote authentication finish from fresh, protected-safe semantic inventory evidence after
selector drift, while retaining code-owned cookie-capture authority, bounded Sonnet/Opus policy,
exact terminal reasons, and owner-visible maintenance diagnostics.

## Stories Included

- **US-134**: Classify the current page with LLM fallback (Must)
- **US-135**: Recover and interpret safe DOM drift (Must)
- **US-136**: Explain every terminal browser outcome (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ✅ **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- ✅ **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- ✅ **3. ADR Analysis**: Complete → no new ADR; applies ADR-032/033/034
- ✅ **4. Implement**: Complete → remote-auth resilience source
- ✅ **5. Test**: Complete → `ddd-03-test-report.md`

## Dependencies

### Requires

- Bolt 042 protected-first page classification and remote-auth step registry.
- Bolt 043 grounded semantic evidence and canonical terminal diagnosis.
- Bolt 044 post-cleanup incident recording and owner notification.

### Enables

- Corrective release qualification and VPS deployment.

## Expected Outputs

- One-probe-per-stable-page policy that cannot starve adaptive classification.
- Grounded, code-verified semantic inventory proof for selector-drifted `/mytrips` pages.
- Content-free probe/resolver outcome telemetry and exact terminal diagnosis.
- Production-shaped regression coverage for redirect loops, LLM recovery, and protected states.

## Success Criteria

- [x] A signed-in `/mytrips` page with changed selectors completes `/connect` without repeated reloads.
- [x] A failed fixed probe reaches Sonnet once per stable fingerprint and eligible Opus diagnosis.
- [x] Model output alone cannot save cookies; code validates destination, protected-state absence,
  freshness, and grounded structural evidence.
- [x] Auth, MFA, captcha, bot wall, provider, budget, and observation outcomes remain exact.
- [x] Unresolved DOM drift records an owner-visible incident after browser cleanup.
- [x] Focused and full repository quality gates pass.

## Notes

This bolt corrects accepted ADR-032 behavior; it does not expand browser action authority or allow
models to enter credentials, solve challenges, mutate reservations, or provide arbitrary selectors.
