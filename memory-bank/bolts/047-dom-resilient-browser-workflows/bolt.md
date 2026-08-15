---
id: 047-dom-resilient-browser-workflows
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
type: ddd-construction-bolt
status: complete
stories:
  - 005-finalize-verified-remote-authentication-atomically
created: 2026-08-15T15:55:59.000Z
started: 2026-08-15T15:55:59.000Z
completed: "2026-08-15T16:06:42Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-08-15T15:57:07.000Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-15T15:59:19.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-15T15:59:19.000Z
    artifact: none-required-existing-adrs-024-026-032-033-034
  - name: implement
    completed: 2026-08-15T16:04:46.000Z
    artifact: source-code-and-merge-gate
  - name: test
    completed: 2026-08-15T16:06:12.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 044-dom-drift-incident-operations
  - 045-dom-resilient-browser-workflows
  - 046-dom-resilient-browser-workflows
enables_bolts: []
requires_units:
  - 002-dom-resilient-browser-workflows
  - 003-dom-drift-incident-operations
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 047-dom-resilient-browser-workflows

## Overview

Correct two post-merge review races in remote-auth finalization and make completion of delayed
Cursor Bugbot review a hard pre-merge release gate.

## Objective

Ensure a code-verified finalizing attempt cannot lose encrypted capture to ordinary expiry; retain
eligible sanitized failure incidents when viewer cancellation or expiry wins; preserve user
purge/revocation and daemon-shutdown evidence boundaries; and prevent future merges before every
Bugbot concern has a documented disposition and clean follow-up pass.

## Stories Included

- **US-140**: Finalize verified remote authentication atomically (Must, corrective coverage)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ✅ **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- ✅ **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- ✅ **3. ADR Analysis**: Complete → no new ADR; applies ADR-024/026/032/033/034
- ✅ **4. Implement**: Complete → remote-auth race repair and executable merge gate
- ✅ **5. Test**: Complete → `ddd-03-test-report.md`

## Dependencies

### Requires

- Bolt 044 encrypted incident retention and user-purge boundary.
- Bolt 045 grounded remote-auth DOM recovery and post-cleanup incident draft.
- Bolt 046 finalizing state, source-aware cancellation authority, capture ordering, and viewer state.

### Enables

- Follow-up review and release with a completed Bugbot gate.

## Expected Outputs

- Finalizing-expiry precedence that cannot discard code-verified session capture.
- Source-aware post-cleanup failure-incident disposition that cannot recreate purged evidence.
- Focused deterministic concurrency regressions for expiry, viewer cancellation, purge, and shutdown.
- Durable repository/runbook merge gate for delayed Bugbot review and follow-up validation.

## Success Criteria

- [x] Crossing ordinary `expires_at` during `FINALIZING` cannot change the attempt to `EXPIRED`.
- [x] Administrative purge/revocation and daemon shutdown still prevent session persistence.
- [x] Eligible failed-result incidents survive viewer-cancel and expiry races after browser cleanup.
- [x] Purge/revocation never recreates encrypted evidence or an incident occurrence after deletion.
- [x] Future merge handoffs require a completed Bugbot pass, disposition of every unresolved thread,
  and a clean follow-up pass for the final reviewed commit.
- [x] Focused concurrency tests and the full repository quality gate pass.

## Notes

Bugbot's first proposed correction is safe. Its unconditional failure-incident publication is not:
publishing after administrative purge could recreate user-linked encrypted evidence. This bolt
therefore models incident eligibility by cancellation authority instead of moving the sink call
outside the terminal-state guard without qualification.
