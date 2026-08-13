---
id: 043-dom-resilient-browser-workflows
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
type: ddd-construction-bolt
status: complete
stories:
  - 003-recover-and-interpret-safe-dom-drift
  - 004-explain-every-terminal-browser-outcome
created: 2026-08-13T01:59:59.000Z
started: 2026-08-13T03:08:00.000Z
completed: "2026-08-13T03:30:09Z"
current_stage: null
stages_completed:
  - domain-model
  - technical-design
  - adr-analysis
requires_bolts:
  - 042-dom-resilient-browser-workflows
enables_bolts:
  - 044-dom-drift-incident-operations
requires_units:
  - 001-adaptive-model-policy
blocks: true
complexity:
  avg_complexity: 3
  avg_uncertainty: 3
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 043-dom-resilient-browser-workflows

## Overview

Apply adaptive model navigation, typed semantic interpretation, narrow safe popup adoption, and
reason-preserving termination to every registered account and customer-search DOM seam.

## Objective

Ensure Booking.com selector/copy/control drift can be recovered without code changes when safe.
Known outcomes terminate under exact deterministic reasons with zero diagnosis cost; only unresolved
ambiguous work receives an Opus diagnosis rather than a generic browser failure.

## Stories Included

- **US-135**: Recover and interpret safe DOM drift (Must)
- **US-136**: Explain every terminal browser outcome (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. ADR Analysis**: Complete → ADR-033 accepted
- [ ] **4. Implement**: In progress → browser/inventory/search/extraction/outcome integration
- [ ] **5. Test**: Pending → `ddd-03-test-report.md`

## Dependencies

### Requires

- `042-dom-resilient-browser-workflows` step registry and page classifier.
- Existing account completeness, offer equivalence, currency, session, ActionGuard, coordinator, and
  caller-scoped audit boundaries.

### Enables

- `044-dom-drift-incident-operations`.

## Expected Outputs

- Per-step accessible-control policy and one-popup adoption guard.
- Typed semantic postcondition, reservation, and offer evidence validation.
- Shared final diagnostic seam and complete terminal reason taxonomy/provenance.
- Cross-trigger regression fixtures for inventory, `/connect`, `/checknow`, scheduler, and price search.

## Success Criteria

- [ ] Changed safe controls and one allowlisted popup recover without new selectors.
- [ ] Model facts never replace code-owned identity/completeness/equivalence/refundability/currency rules.
- [ ] Registered DOM paths cannot fall through to generic unknown/navigation/extraction results.
- [ ] Opus diagnoses eligible ambiguous DOM work without receiving action authority; known failures
  use zero diagnosis calls.
- [ ] All failure paths preserve state and release browser/coordinator resources.
- [ ] Focused and full relevant quality gates pass.

## Notes

The popup allowance is deliberately narrow: one observable, allowlisted, read-only Booking.com page
opened by the current guarded action. Unknown, protected, external, mutating, or additional popups
remain hard stops.
