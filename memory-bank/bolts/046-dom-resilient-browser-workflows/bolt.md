---
id: 046-dom-resilient-browser-workflows
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
type: ddd-construction-bolt
status: complete
stories:
  - 005-finalize-verified-remote-authentication-atomically
created: 2026-08-14T03:08:12.000Z
started: 2026-08-14T03:10:57.000Z
completed: "2026-08-14T03:21:03Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-08-14T03:11:51.000Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-14T03:13:01.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-14T03:13:01.000Z
    artifact: none-required-existing-adrs-024-026-032-033-034
  - name: implement
    completed: 2026-08-14T03:19:00.000Z
    artifact: source-code
  - name: test
    completed: 2026-08-14T03:21:03.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 031-remote-auth-attempt-recovery
  - 043-dom-resilient-browser-workflows
  - 044-dom-drift-incident-operations
  - 045-dom-resilient-browser-workflows
enables_bolts: []
requires_units:
  - 002-dom-resilient-browser-workflows
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 046-dom-resilient-browser-workflows

## Overview

Correct the production race in which code verifies the changed Booking.com inventory DOM, but an
ordinary Mini App close cancels the attempt before the manager persists cookies and commits success.

## Objective

Make remote-auth finalization atomic and observable across the browser runner, application manager,
encrypted session repository, DOM-incident recorder, Telegram viewer, and administrative purge
boundary without expanding model or browser authority.

## Stories Included

- **US-140**: Finalize verified remote authentication atomically (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ✅ **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- ✅ **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- ✅ **3. ADR Analysis**: Complete → no new ADR; applies ADR-024/026/032/033/034
- ✅ **4. Implement**: Complete → remote-auth manager/runner/viewer/runtime source
- ✅ **5. Test**: Complete → `ddd-03-test-report.md`

## Dependencies

### Requires

- Bolt 031 pagehide cancellation and same-user attempt recovery.
- Bolt 043 code verification receipt and exact remote-auth diagnosis.
- Bolt 044 post-cleanup incident recording.
- Bolt 045 grounded semantic authentication recovery.

### Enables

- Owner-reviewed merge, deployment, and renewed Telegram `/connect` acceptance.

## Expected Outputs

- Typed finalizing phase with cancellation-source precedence.
- Session persistence before committed success and recovered-incident publication.
- Success-only Telegram Mini App auto-close and safe finalization failure guidance.
- Content-free finalization logs and production-shaped race regressions.

## Success Criteria

- [x] Ordinary viewer close cannot cancel after code verification begins finalization.
- [x] Pre-verification cancel, administrative purge, revocation, and daemon shutdown remain safe.
- [x] Capture success precedes success state, recovered incident, notification, and auto-close.
- [x] Capture failure produces no false recovery and no saved session.
- [x] Focused browser/manager/viewer/purge tests and the full repository gate pass.

## Notes

The fix changes lifecycle ordering only. It does not authorize model-only authentication, persist
before browser cleanup, weaken purge/revocation, expose browser content, or add a second coordinator.
