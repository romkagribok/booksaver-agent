---
id: 049-dom-resilient-browser-workflows
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
type: ddd-construction-bolt
status: complete
stories:
  - 007-admit-edge-pending-negative-control
created: 2026-08-16T16:23:56.000Z
started: 2026-08-16T16:23:56.000Z
completed: "2026-08-16T16:32:36Z"
current_stage: null
stages_completed:
  - domain-model
  - technical-design
  - adr-analysis
  - implement
  - test
requires_bolts:
  - 048-dom-resilient-browser-workflows
enables_bolts: []
requires_units:
  - 003-dom-drift-incident-operations
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 049-dom-resilient-browser-workflows

## Overview

Correct server-contract v1 after live VPS evidence showed Booking consistently returns an exact
empty `202 text/html` response to the fresh cookie-free protected-account probe.

## Objective

Admit the observed tuple only as signed-out/pending evidence under contract v2 while preserving the
unchanged two-probe authenticated receipt boundary.

## Stories Included

- **US-142**: Admit the observed edge-pending negative control safely (Must)

## Stages

- [x] **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. ADR Analysis**: Complete; ADR-035 amended for contract v2
- [x] **4. Implement**: Complete → contract-v2 verifier and operator guidance
- [x] **5. Test**: Complete → `ddd-03-test-report.md`

## Dependencies

- Bolt 048 server-backed verifier and ADR-035.
- Bolt 044 content-free incident operations.
- Bolts 046–047 atomic finalization and merge gate.

## Expected Outputs

- Contract-v2 exact negative predicate for cookie-free edge-pending responses.
- Unchanged exact positive predicate and bound receipt authority.
- Regression tests across baseline, candidate, malformed `202`, privacy, and runner behavior.
- ADR-035 and operator documentation aligned to the v2 contract.

## Success Criteria

- [x] A live-observed exact empty `202` admits the viewer but never a receipt.
- [x] Candidate `202` remains interactive and bounded rather than terminal.
- [x] Only two exact bounded `200` responses issue a receipt.
- [x] All malformed variants fail closed with zero model calls.
- [x] Focused security tests and the full repository gate pass.
