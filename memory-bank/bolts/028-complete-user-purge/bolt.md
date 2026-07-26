---
id: 028-complete-user-purge
unit: 001-complete-user-purge
intent: 015-authentication-boundary-hardening
type: simple-construction-bolt
status: complete
stories:
  - 001-remove-encrypted-authentication-state
  - 002-prevent-inflight-authentication-survival
created: 2026-07-26T19:41:07.000Z
started: 2026-07-26T19:45:19.000Z
completed: "2026-07-26T21:35:50Z"
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-26T21:12:10.000Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-26T21:18:54.000Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-26T21:35:21.000Z
    artifact: test-walkthrough.md
requires_bolts:
  - 009-user-access-and-keys
  - 024-per-user-booking-sessions
  - 026-remote-authentication-gateway
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 028-complete-user-purge

## Objective

Coordinate remote-auth cancellation, encrypted-session deletion, and existing database cleanup so
confirmed purge is complete and race-safe.

## Stories Included

- **001-remove-encrypted-authentication-state**: Remove encrypted authentication state (Must)
- **002-prevent-inflight-authentication-survival**: Prevent in-flight authentication survival (Must)

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

## Stages

- [x] **1. Plan**: Complete → `implementation-plan.md`
- [x] **2. Implement**: Complete → source and tests
- [x] **3. Test**: Complete → `test-walkthrough.md`

## Dependencies

### Requires

- Bolts 009, 024, and 026 (Complete).

### Enables

- Complete user offboarding deployment.

## Success Criteria

- [x] Both stories implemented and acceptance criteria met.
- [x] File deletion failure cannot produce a false successful purge.
- [x] Capture-versus-purge and import-versus-purge races cannot retain or recreate the target
  session.
- [x] Targeted and full tests pass.

## Execution Authorization

The product owner explicitly requested the purge correction. Construction through Test is
authorized; commit, push, merge, and deployment remain held.
