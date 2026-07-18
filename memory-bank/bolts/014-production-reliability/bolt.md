---
id: 014-production-reliability
unit: 001-production-reliability
intent: 004-production-hardening
type: simple-construction-bolt
status: complete
stories:
  - 005-enter-search-from-trusted-query
created: 2026-07-18T18:57:24Z
started: 2026-07-18T18:57:24Z
completed: 2026-07-18T19:25:20Z
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-18T19:14:54Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-18T19:22:47Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-18T19:25:07Z
    artifact: test-walkthrough.md
requires_bolts:
  - 013-production-reliability
enables_bolts: []
requires_units:
  - 001-search-journey-monitor
  - 002-agentic-escalation
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: 014-production-reliability

## Overview

Correct the production behavior revealed by the second VPS trace: the safe trusted-query path works,
but BookSaver reaches it only after homepage `fill_search` recovery consumes nearly the entire shared
time and LLM budget. This bolt promotes the existing Booking.com search-results query to the primary
journey entry and leaves downstream scripted verification plus guarded LLM recovery intact.

## Objective

Begin every price check at Booking.com's exact search-results query generated from persisted booking
data, eliminating visual homepage form interaction while preserving the full results-to-property-to-
room-table price-verification journey and all savings safety gates.

## Stories Included

- [x] **005-enter-search-from-trusted-query / US-041**: Skip homepage form entry and preserve verified
  downstream search, LLM recovery, extraction, and savings behavior (Must).

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

This is a bounded correction inside the existing `SearchJourney` seam. It adds no domain entity,
persistence model, dependency, service, or external integration.

## Stages

- ✅ **1. Plan**: Complete → `implementation-plan.md`
- ✅ **2. Implement**: Complete → source/tests + `implementation-walkthrough.md`
- ✅ **3. Test**: Complete → verification + `test-walkthrough.md`

Each stage retains the simple-bolt mandatory human checkpoint.

## Dependencies

### Requires

- Bolt `013-production-reliability`: trusted-query continuation and production trace evidence.
- Intent 002 search journey and agentic escalation: result verification, room extraction, guarded
  recovery, budgets, and trace contracts.

### Enables

- VPS redeployment and a live Telegram check with downstream agent budget available.

## Success Criteria

- [x] No active journey step fills or submits Booking.com's homepage form.
- [x] Search-results navigation uses only persisted property, dates, and occupancy.
- [x] Exact property and search context remain mandatory before offer extraction.
- [x] LLM recovery remains available for downstream layout/interpretation failures.
- [x] Existing equivalence, refundability, safety, and savings behavior remains unchanged.
- [x] Focused and full automated/static verification passes.
- [x] Code and AI-DLC artifacts received human review before commit/push.

## Notes

ADR-013 explicitly selected homepage form entry as part of the full journey. Construction must record
an ADR amendment explaining why production evidence now favors direct search-results entry without
changing the room-table price source or permitting a direct registered-property deep link.
