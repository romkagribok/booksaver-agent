---
id: 042-dom-resilient-browser-workflows
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
type: ddd-construction-bolt
status: complete
stories:
  - 001-register-every-dom-sensitive-browser-step
  - 002-classify-current-page-with-llm-fallback
created: 2026-08-13T01:59:59.000Z
started: 2026-08-13T02:39:01.000Z
completed: "2026-08-13T03:30:09Z"
current_stage: null
stages_completed:
  - domain-model
  - technical-design
  - adr-analysis
  - implement
  - test
requires_bolts:
  - 040-agent-assisted-booking-inventory
  - 041-adaptive-model-policy
enables_bolts:
  - 043-dom-resilient-browser-workflows
requires_units:
  - 001-adaptive-model-policy
  - 002-agent-assisted-booking-inventory
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 042-dom-resilient-browser-workflows

## Overview

Create the exhaustive DOM-step coverage contract and replace weak boolean authentication/session
heuristics with protected-state-first deterministic classification, zero-call known outcomes, and
bounded Sonnet/Opus fallback only for ambiguity.

## Objective

Make every DOM-dependent Booking.com seam visible to the resilience controller and fix the current
production failure where an LLM authentication conclusion is collapsed into generic inventory
`gave_up` without marking the session reauth-required.

## Stories Included

- **US-133**: Register every DOM-sensitive browser step (Must)
- **US-134**: Classify the current page with LLM fallback (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. ADR Analysis**: Complete → ADR-032 accepted
- [x] **4. Implement**: Complete → step registry, protected-first classifier, exact auth mapping
- [x] **5. Test**: Complete → `ddd-03-test-report.md`

## Dependencies

### Requires

- `040-agent-assisted-booking-inventory` current-page recovery baseline.
- `041-adaptive-model-policy` routing and dollar admission.
- Existing Playwright adapter, remote-auth runner, inventory/search workflows, session manager,
  coordinator, and deterministic verifiers.

### Enables

- `043-dom-resilient-browser-workflows`.

## Expected Outputs

- Typed DOM-step registry and structural coverage test.
- Protected-state-first current-page assessment and typed LLM classifier port/adapter.
- Correct zero-call authentication/captcha/provider/budget reason propagation and reauth transition.
- Production-shaped false-positive signed-in and model-auth regression fixtures.

## Success Criteria

- [x] Every current DOM-sensitive step declares exact terminal behavior and ambiguity fallback.
- [x] Changed login DOM cannot be accepted from weak account-link/Genius markers.
- [x] Model `authentication_required` becomes domain auth-required and `/connect` guidance.
- [x] An LLM authenticated claim alone cannot save or extend a session.
- [x] Protected pages execute zero model browser actions.
- [x] Focused and full relevant quality gates pass.

## Notes

Bolt 041 completed before this bolt entered implementation; the dependency is satisfied.
