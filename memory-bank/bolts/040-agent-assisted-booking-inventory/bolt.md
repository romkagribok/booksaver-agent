---
id: 040-agent-assisted-booking-inventory
unit: 002-agent-assisted-booking-inventory
intent: 021-booking-browser-llm-recovery
type: ddd-construction-bolt
status: complete
stories:
  - 004-recover-initial-inventory-navigation-from-current-evidence
created: 2026-08-10T16:36:20.000Z
started: 2026-08-10T16:39:46.000Z
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-08-10T16:39:46.000Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-10T16:40:38.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-10T16:40:38.000Z
    artifact: skipped-adr-030-and-adrs-027-028-govern
  - name: implement
    completed: 2026-08-10T16:43:59.000Z
  - name: test
    completed: 2026-08-10T16:47:05.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 039-agent-assisted-booking-inventory
enables_bolts: []
requires_units:
  - 001-shared-booking-browser-recovery
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 3
completed: "2026-08-10T16:47:19Z"
---

# Bolt: 040-agent-assisted-booking-inventory

## Overview

Correct the production initial-navigation recovery handoff that classified stale `about:blank`
evidence after an authenticated Booking.com inventory-readiness exception.

## Objective

Use fresh post-failure page evidence for safety classification and guarded recovery while retaining
the pre-navigation observation only as a verification baseline. Add content-free diagnostics and
deterministic regression coverage without widening routes, weakening completeness, or enabling any
new browser action.

## Stories Included

- **US-129**: Recover initial inventory navigation from current evidence (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. ADR Analysis**: Skipped → ADR-030 and ADRs 027–028 govern
- [x] **4. Implement**: Complete → fresh post-failure evidence and bounded diagnostics
- [x] **5. Test**: Complete → `ddd-03-test-report.md`

## Dependencies

### Requires

- `039-agent-assisted-booking-inventory`.
- Existing ADR-027 account authority, ADR-028 completeness gating, and ADR-030 guarded recovery.

### Enables

- Reviewed pull request, production deployment planning, and human `/bookings` then `/checknow`
  acceptance.

## Success Criteria

- [x] Available current evidence always supersedes stale pre-navigation evidence for safety checks.
- [x] Unavailable, authentication, captcha, and unapproved current pages remain fail closed.
- [x] Diagnostics contain bounded categories only and expose no page/account content.
- [x] Production-shaped deterministic regressions and broader repository gates pass.
- [x] Commit, push, and pull request are prepared; merge remains blocked on owner review.

## Notes

The owner pre-authorized progression through construction, verification, commit, push, and pull
request preparation. Stop immediately before merge. Deployment remains separately gated.
