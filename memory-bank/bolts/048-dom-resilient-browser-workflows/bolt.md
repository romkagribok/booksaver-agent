---
id: 048-dom-resilient-browser-workflows
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
type: ddd-construction-bolt
status: complete
stories:
  - 006-verify-remote-authentication-from-server-evidence
created: 2026-08-15T22:33:19.000Z
started: 2026-08-15T22:33:19.000Z
completed: 2026-08-15T23:16:21Z
current_stage: complete
stages_completed:
  - domain-model
  - technical-design
  - adr-analysis
  - implement
  - test
requires_bolts:
  - 042-dom-resilient-browser-workflows
  - 044-dom-drift-incident-operations
  - 046-dom-resilient-browser-workflows
  - 047-dom-resilient-browser-workflows
enables_bolts: []
requires_units:
  - 003-dom-drift-incident-operations
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 048-dom-resilient-browser-workflows

## Overview

Remove reservation DOM and LLM classification from `/connect` success authority. Verify candidate
Booking.com cookies through a versioned, isolated, read-only server contract and hand a bound
single-use receipt to the existing atomic session-finalization lifecycle.

## Objective

Make remote authentication insensitive to Booking.com presentation changes without weakening
session ownership, protected challenge handling, encrypted persistence, cancellation precedence,
privacy, or fail-closed behavior.

## Stories Included

- **US-141**: Verify remote authentication from server evidence (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. ADR Analysis**: ADR-035 accepted
- [x] **4. Implement**: Complete → source and tests
- [x] **5. Test**: Complete → `ddd-03-test-report.md`

## Dependencies

### Requires

- Bolt 042 typed page-state boundary and protected outcomes.
- Bolt 044 content-free maintenance incidents.
- Bolts 046–047 atomic finalization, cancellation precedence, evidence disposition, and merge gate.

### Enables

- A `/connect` flow whose authentication result does not depend on reservation DOM.

## Expected Outputs

- Versioned Booking server-session contract and code-owned receipt.
- Fresh isolated negative and positive verification contexts.
- Candidate-cookie stabilization and exact-snapshot finalization.
- Typed contract, transport, redirect, challenge, and cancellation outcomes.
- Content-free verifier telemetry and maintenance incident evidence.
- Removal of DOM/LLM authority from the `/connect` success path.

## Success Criteria

- [x] Exact server evidence is the sole `/connect` authentication authority.
- [x] URL, cookie, DOM, and model signals cannot independently or jointly create a receipt.
- [x] The verified cookie snapshot is the snapshot encrypted by finalization.
- [x] Predictable signed-out results keep the viewer open with zero LLM calls.
- [x] Contract drift fails closed and produces actionable content-free owner evidence.
- [x] Existing viewer, purge, revocation, shutdown, and persistence races remain safe.
- [x] Focused security/integration tests and the full repository quality gate pass.

## Notes

Live content-free discovery established contract v1: a fresh empty context receives `302` to the
Booking OAuth route for `GET https://secure.booking.com/myaccount.html`, while the current
authenticated cookie snapshot receives a direct bounded `200 text/html`. The implementation must
revalidate this negative control at attempt start and confirm the positive result twice; it must not
generalize arbitrary status codes or endpoints into authentication authority.
