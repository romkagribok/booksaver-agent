---
id: 015-production-reliability
unit: 001-production-reliability
intent: 004-production-hardening
type: simple-construction-bolt
status: complete
stories:
  - 006-handle-property-availability-page
created: 2026-07-18T20:00:27.000Z
started: 2026-07-18T20:00:27.000Z
completed: "2026-07-18T21:47:06Z"
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-18T20:00:27.000Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-18T20:08:36.000Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-18T20:10:28.000Z
    artifact: test-walkthrough.md
requires_bolts:
  - 014-production-reliability
enables_bolts: []
requires_units:
  - 001-search-journey-monitor
  - 002-agentic-escalation
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: 015-production-reliability

## Overview

Correct the property-page failure captured by the first query-first VPS check. Booking.com loaded the
right hotel, but a consent panel covered the page, the property showed “Check available dates,” and
`open_property` required one of two legacy room-table selectors before context verification could run.

## Objective

Make property loading, context verification, and room/availability interpretation distinct, bounded
steps so the agent can adapt to the price-bearing page without clicking blindly or weakening savings
safety.

## Stories Included

- [x] **006-handle-property-availability-page / US-042**: Preserve trusted property context, dismiss
  consent overlays, and interpret room/availability state semantically (Must).

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

## Stages

- ✅ **1. Plan**: Complete under the product owner's authorized continuous-flow exception →
  `implementation-plan.md`
- ✅ **2. Implement**: Complete under the product owner's authorized continuous-flow exception →
  source/tests + `implementation-walkthrough.md`
- ✅ **3. Test**: Complete under the product owner's authorized continuous-flow exception →
  verification + `test-walkthrough.md`

All stages and the mandatory final human gate are complete. The official completion script updated
the bolt, story, unit, and intent statuses on 2026-07-18T21:47:06Z.

The product owner explicitly authorized autonomous progression through intermediate checkpoints and
requested one approval immediately before the official bolt-completion gate.

## Dependencies

### Requires

- Bolt `014-production-reliability`: trusted query-first search entry.
- Intent 002 search journey and agentic escalation: verified offers, guarded actions, budgets, traces.

### Enables

- VPS redeployment and a Telegram smoke test with a meaningful property availability outcome.

## Success Criteria

- [x] Fresh result href retains every persisted date/occupancy parameter.
- [x] Consent overlays are dismissed after navigation without LLM spend.
- [x] Property loading no longer requires a legacy room-table selector.
- [x] Full context verification precedes rate interpretation.
- [x] Known or semantic rate content reaches existing offer extraction.
- [x] Explicit no availability maps promptly to `NO_EQUIVALENT_OFFER`.
- [x] Downstream screenshot-first LLM recovery and all safety guards remain intact.
- [x] Focused/full tests, Ruff, mypy, and memory-bank consistency pass.

## Notes

Evidence source: VPS check `35c4ce8b-3e2a-4ed3-abe6-6fd38b86dc12` and its saved screenshot.
