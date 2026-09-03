---
id: 065-shared-browser-use-access
unit: 007-shared-browser-use-access
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 001-route-disclosed-invitees-through-browser-use
  - 002-show-secret-safe-api-key-provenance
created: 2026-09-03T23:30:00.000Z
started: 2026-09-03T23:35:00.000Z
completed: "2026-09-03T23:40:07Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-09-03T23:36:00.000Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-09-03T23:38:00.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-09-03T23:39:00.000Z
    artifact: adr-045-explicit-consented-user-browser-use-rollout.md, adr-046-secret-safe-admin-api-funding-provenance.md
  - name: implement
    completed: 2026-09-03T23:40:00.000Z
    artifact: source-and-tests
  - name: test
    completed: 2026-09-03T23:40:06.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 064-browser-use-price-executor
enables_bolts: []
requires_units:
  - 001-agentic-executor-control-plane
  - 004-agentic-inventory-executor
  - 006-browser-use-price-executor
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: 065-shared-browser-use-access

## Overview

Add an explicit consented-user Browser Use rollout and an owner-only secret-safe API funding
projection without weakening BookSaver's disclosure, validation, or secret boundaries.

## Objective

Complete US-170 and US-171 so disclosed invited users share the owner's Browser Use path and the
Telegram owner can see effective funding provenance without seeing API-key material.

## Stories Included

- **001-route-disclosed-invitees-through-browser-use**: Consented invitee Browser Use parity (Must)
- **002-show-secret-safe-api-key-provenance**: Safe admin funding/key-presence display (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ✅ **1. domain-model**: Complete → `ddd-01-domain-model.md`
- ✅ **2. technical-design**: Complete → `ddd-02-technical-design.md`
- ✅ **3. adr-analysis**: Complete → ADR-045 and ADR-046
- ✅ **4. implement**: Complete → routing, configuration, documentation, and admin projection
- ✅ **5. test**: Complete → `ddd-03-test-report.md`

## Dependencies

### Requires

- Bolt 064 Browser Use price and inventory execution.
- Existing disclosure and regression state from Unit 003, plus user aggregate and Telegram owner
  gates. The unfinished live qualification checkpoint is not a construction prerequisite.

### Enables

- Production configuration and deployment of shared Browser Use access.

## Success Criteria

- [x] All stories implemented.
- [x] All acceptance criteria met.
- [x] Existing safety and privacy boundaries remain tested.
- [x] Focused and full repository checks pass.

## Merge Gate

Cursor Bugbot must review the exact final head before merge. This post-bolt repository gate is
tracked on the pull request so satisfying it does not require a new, immediately stale commit.

## Notes

The user explicitly authorized inception, all construction checkpoints, final review, and merge in
the 2026-09-03 directive. Production deployment remains a later operation.
