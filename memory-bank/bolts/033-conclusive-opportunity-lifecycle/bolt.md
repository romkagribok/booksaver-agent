---
id: 033-conclusive-opportunity-lifecycle
unit: 001-conclusive-opportunity-lifecycle
intent: 018-conclusive-rebook-opportunity-lifecycle
type: simple-construction-bolt
status: complete
stories:
  - 001-preserve-opportunity-across-technical-failures
  - 002-supersede-opportunity-on-conclusive-check
  - 003-enforce-conclusive-currentness-atomically
created: 2026-07-27T02:32:08.000Z
started: 2026-07-27T02:34:15.000Z
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-27T02:34:43.000Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-27T02:39:16.000Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-27T02:40:04.000Z
    artifact: test-walkthrough.md
requires_bolts:
  - 032-current-rebook-opportunities
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 2
completed: "2026-07-27T02:40:33Z"
reviewed: 2026-07-27T02:46:10Z
---

# Bolt: 033-conclusive-opportunity-lifecycle

## Overview

Refine current savings selection with conclusive check-history semantics.

## Objective

Preserve the last verified saving across technical failures while ensuring later successful or
no-equivalent market results replace or invalidate its rebook actionability.

## Stories Included

- [x] **001-preserve-opportunity-across-technical-failures**: Preserve opportunity across technical failures - Must
- [x] **002-supersede-opportunity-on-conclusive-check**: Supersede opportunity on conclusive check - Must
- [x] **003-enforce-conclusive-currentness-atomically**: Enforce conclusive currentness atomically - Must

## Expected Outputs

- Check-linked current-opportunity SQLite policy.
- Matching transactional session guard.
- Accurate Telegram stale-selection guidance.
- Focused persistence, service, Telegram, and history tests.
- Full verification and AI-DLC completion artifacts.

## Dependencies

- **032-current-rebook-opportunities**: Provides one-per-booking selection and stale-ID guards.

## Enables

None currently planned.

## Success Criteria

- [x] Technical failures preserve the last conclusive positive choice.
- [x] Later successful smaller savings replace larger historical savings.
- [x] Later successful non-saving and `NO_EQUIVALENT_OFFER` results remove actionability.
- [x] A later positive success restores actionability.
- [x] Picker, shared service, and atomic session guard agree.
- [x] History, ownership, and human-action boundaries remain intact.
- [x] Focused and full quality gates pass.
- [ ] Final product-owner merge review is complete.

## Execution Authorization

The product owner authorized uninterrupted execution through final pre-merge review. Commit, push,
merge, and deployment remain held for separate approval.
