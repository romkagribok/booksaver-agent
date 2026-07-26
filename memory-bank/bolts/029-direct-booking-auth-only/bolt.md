---
id: 029-direct-booking-auth-only
unit: 002-direct-booking-auth-only
intent: 015-authentication-boundary-hardening
type: simple-construction-bolt
status: complete
stories:
  - 001-block-external-provider-navigation
  - 002-guide-direct-booking-login
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
  - 026-remote-authentication-gateway
  - 027-remote-auth-display-reliability
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 1
  avg_uncertainty: 1
  max_dependencies: 1
  testing_scope: 2
---

# Bolt: 029-direct-booking-auth-only

## Objective

Restrict remote-auth interactive navigation to Booking.com-owned pages and clearly explain that
users must use direct Booking.com credentials.

## Stories Included

- **001-block-external-provider-navigation**: Block external provider navigation (Must)
- **002-guide-direct-booking-login**: Guide direct Booking.com login (Must)

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

## Stages

- [x] **1. Plan**: Complete → `implementation-plan.md`
- [x] **2. Implement**: Complete → source and tests
- [x] **3. Test**: Complete → `test-walkthrough.md`

## Dependencies

### Requires

- Bolts 026 and 027 (Complete).

### Enables

- Direct Booking.com authentication acceptance testing.

## Success Criteria

- [x] Both stories implemented and acceptance criteria met.
- [x] External main-page, child-frame, and popup provider navigation is blocked without breaking
  direct Booking.com login.
- [x] Telegram and viewer guidance is explicit and safe.
- [x] Targeted and full tests pass.

## Execution Authorization

The product owner explicitly requested provider sign-in be disabled. Construction through Test is
authorized; commit, push, merge, and deployment remain held.
