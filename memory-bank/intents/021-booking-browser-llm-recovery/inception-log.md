---
intent: 021-booking-browser-llm-recovery
created: 2026-08-02T18:07:49Z
completed: 2026-08-02T18:07:49Z
status: complete
---

# Inception Log: Booking Browser LLM Recovery

## Overview

**Intent**: Make every automated read-only Booking.com browser journey recover through one guarded,
progress-aware LLM boundary and extend it to authoritative account inventory.
**Type**: Brown-field reliability enhancement.
**Created**: 2026-08-02T18:07:49Z

## Artifacts Created

| Artifact | Status | File |
|----------|--------|------|
| Requirements | Complete | `requirements.md` |
| System Context | Complete | `system-context.md` |
| Units | Complete | `units.md` and two unit briefs |
| Stories | Complete | Seven story files |
| Bolt Plan | Complete | `memory-bank/bolts/038-*` and `039-*` |

## Summary

| Metric | Count |
|--------|-------|
| Functional Requirements | 9 |
| Non-Functional Requirement Groups | 4 |
| Units | 2 |
| Stories | 7 |
| Bolts Planned | 2 |

## Units Breakdown

| Unit | Stories | Bolts | Priority |
|------|---------|-------|----------|
| `001-shared-booking-browser-recovery` | 4 | 1 | Must |
| `002-agent-assisted-booking-inventory` | 3 | 1 | Must |

## Decision Log

| Date | Decision | Rationale | Approved |
|------|----------|-----------|----------|
| 2026-08-02 | Treat normal action execution as distinct from verified progress | Production trace showed repeated successful clicks against an unchanged active page | Yes |
| 2026-08-02 | Apply LLM fallback to all automated Booking.com journeys | Account discovery for one user failed after page drift and had no recovery seam | Yes |
| 2026-08-02 | Exclude human-controlled login from LLM action scope | Credentials and MFA must remain human-only | Yes |
| 2026-08-02 | Preserve deterministic completeness authority | Model output cannot safely prove absence across a complete account | Yes |
| 2026-08-02 | Proceed autonomously through construction and verification | Product owner requested completion before a pre-merge review | Yes |

## Scope Changes

| Date | Change | Reason | Impact |
|------|--------|--------|--------|
| 2026-08-02 | Expanded from price-check LLM behavior to all automated Booking.com browser work | `/bookings` discovery also fails on layout drift | Added a second unit and bolt for inventory recovery |

## Ready for Construction

- [x] All requirements documented and approved through the owner's autonomous-progression instruction.
- [x] System context defined.
- [x] Units decomposed.
- [x] Stories created and indexed.
- [x] Bolts planned.
- [x] Human review checkpoints pre-authorized through verification; merge remains a separate gate.

## Next Steps

1. Execute `038-shared-booking-browser-recovery`.
2. Execute `039-agent-assisted-booking-inventory`.
3. Run focused and full repository verification.
4. Stop before commit, push, PR, merge, or deployment for product-owner review.

## Dependencies

Bolt 038 depends on existing agent/search infrastructure. Bolt 039 depends on bolt 038 and the
account synchronization/synchronized interface bolts.
