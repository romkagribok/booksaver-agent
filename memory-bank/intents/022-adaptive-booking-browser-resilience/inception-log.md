---
intent: 022-adaptive-booking-browser-resilience
created: 2026-08-13T01:51:45Z
completed: 2026-08-13T02:25:17Z
updated: 2026-08-14T03:21:03Z
status: complete
---

# Inception Log: Adaptive Booking Browser Resilience

## Overview

**Intent**: Adapt safely across Booking.com DOM drift, escalate weak model outcomes, and alert the
owner when code maintenance is required.
**Type**: brown-field enhancement and production defect hardening
**Created**: 2026-08-13T01:51:45Z

## Artifacts Created

| Artifact | Status | File |
|----------|--------|------|
| Requirements | Approved | `requirements.md` |
| System Context | Generated | `system-context.md` |
| Units | Generated | `units.md` and three unit briefs |
| Stories | Generated | `units/*/stories/*.md` (11 stories) |
| Bolt Plan | Generated | `memory-bank/bolts/041-*` through `046-*` |

## Summary

| Metric | Count |
|--------|-------|
| Functional Requirements | 11 |
| Non-Functional Requirements | 16 |
| Units | 3 |
| Stories | 11 |
| Bolts Planned | 6 |

## Units Breakdown

| Unit | Stories | Bolts | Priority |
|------|---------|-------|----------|
| `001-adaptive-model-policy` | 3 | 1 (`041`) | Must |
| `002-dom-resilient-browser-workflows` | 5 | 4 (`042`, `043`, `045`, `046`) | Must |
| `003-dom-drift-incident-operations` | 3 | 1 (`044`) | Must |

## Decision Log

| Date | Decision | Rationale | Approved |
|------|----------|-----------|----------|
| 2026-08-13 | Create intent 022 instead of reopening intent 021 | Intent 021 explicitly excluded automatic production model/provider switching | Yes |
| 2026-08-13 | Preserve code-owned safety and truth boundaries | DOM resilience cannot authorize login, unsafe actions, identity guesses, or incomplete reconciliation | Yes |
| 2026-08-13 | Use Sonnet 5 with bounded Opus 5 escalation; exclude Fable | The owner wants automatic replacement of an ineffective model without Fable's cost or complexity | Yes |
| 2026-08-13 | Cap estimated spend at USD 1/job and USD 10/deployment UTC day | Recovery may cost more than immediate failure but must retain a hard, restart-safe ceiling | Yes |
| 2026-08-13 | Retain encrypted incident evidence locally for seven days | Maintenance needs useful evidence while Telegram and logs remain content-free | Yes |
| 2026-08-13 | Require a reasoned terminal outcome for every DOM-sensitive failure | A browser job may not repeat the current generic failure with no LLM diagnosis or exact system reason | Yes |
| 2026-08-13 | Use LLM explanation only for ambiguous failures | Predictable outcomes such as confirmed `/connect` required already have an exact code and action; spending a model call would add cost without information | Yes |
| 2026-08-14 | Commit verified remote auth before viewer close or recovery publication | Production proved that DOM recovery can succeed while pagehide cancellation still discards session capture | Yes |

## Scope Changes

| Date | Change | Reason | Impact |
|------|--------|--------|--------|
| 2026-08-13 | Add model escalation and owner drift incidents | Production recovery reached an approved URL but misclassified re-authentication and could not recover | New resilience, model-routing, and operations units expected |
| 2026-08-14 | Add Bolt 045 for mobile inventory DOM recovery | The fixed legacy probe loop starved classification on `/mytrips` | One corrective DDD bolt completed and deployed |
| 2026-08-14 | Add US-140 and Bolt 046 for atomic finalization | Verified recovery was published before cookie persistence, while pagehide could still cancel | One corrective story and DDD bolt; no authority expansion |

## Ready for Construction

**Checklist**:
- [x] All requirements documented
- [x] System context defined
- [x] Units decomposed
- [x] Stories created for all units
- [x] Bolts planned
- [x] Human review complete

## Next Steps

1. Begin Construction with `041-adaptive-model-policy`.
2. Continue through bolts 042–044 after their required validation stages.
3. Stop at the final pre-merge review gate for owner verification.
4. Present completed corrective Bolt 046 to the owner at the pre-merge review gate.

## Dependencies

`041-adaptive-model-policy` → `042-dom-resilient-browser-workflows` →
`043-dom-resilient-browser-workflows` → `044-dom-drift-incident-operations`
