---
id: 032-current-rebook-opportunities
unit: 001-current-rebook-opportunities
intent: 017-current-rebook-opportunities
type: simple-construction-bolt
status: complete
stories:
  - 001-show-one-current-opportunity-per-booking
  - 002-reject-superseded-rebook-selection
  - 003-preserve-savings-audit-and-access-boundaries
created: 2026-07-27T02:10:44.000Z
started: 2026-07-27T02:14:27.000Z
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-27T02:14:27.000Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-27T02:16:57.000Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-27T02:22:20.000Z
    artifact: test-walkthrough.md
requires_bolts:
  - 011-rebook-confirmation-gate
  - 023-post-rebook-monitoring
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 2
completed: "2026-07-27T02:23:59Z"
---

# Bolt: 032-current-rebook-opportunities

## Overview

Correct current-opportunity selection across persistence, Telegram, and the shared guided-rebook
service.

## Objective

Show at most one newest savings choice per active booking and prevent superseded historical choices
from starting a guided rebook while retaining audit history.

## Stories Included

- **001-show-one-current-opportunity-per-booking**: Show one current opportunity per booking (Must)
- **002-reject-superseded-rebook-selection**: Reject superseded rebook selections (Must)
- **003-preserve-savings-audit-and-access-boundaries**: Preserve savings audit and access boundaries
  (Must)

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

## Stages

- [x] **1. Plan**: Complete → `implementation-plan.md`
- [x] **2. Implement**: Complete → source, tests, and `implementation-walkthrough.md`
- [x] **3. Test**: Complete → `test-walkthrough.md`

## Dependencies

- **011-rebook-confirmation-gate**: Existing explicit confirmation and device handoff (Complete)
- **023-post-rebook-monitoring**: Existing stale-savings cleanup and audit boundary (Complete)

## Success Criteria

- [x] All three stories and acceptance criteria are complete.
- [x] Telegram shows one current choice per active owned booking.
- [x] Stale callbacks/manual IDs create no guided session.
- [x] Historical savings remain queryable.
- [x] Focused and full quality gates pass.
- [ ] Final product-owner merge review is complete.

## Execution Authorization

The product owner authorized uninterrupted AI-DLC construction through final pre-merge review.
Commit, push, merge, and deployment remain held for final approval.
