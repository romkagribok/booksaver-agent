---
intent: 019-booking-account-synchronization
created: 2026-07-27T14:57:11Z
completed: 2026-07-27T16:28:04Z
status: complete
---

# Inception Log: Booking Account Synchronization

## Overview

**Intent**: Replace manually maintained BookSaver booking state with read-only synchronization from
each user's authenticated Booking.com account.
**Type**: Brown-field enhancement and product simplification.
**Created**: 2026-07-27T14:57:11Z

## Artifacts Created

| Artifact | Status | File |
|----------|--------|------|
| Requirements | Approved | `requirements.md` |
| System Context | Approved | `system-context.md` |
| Units | Approved | `units.md` and `units/*/unit-brief.md` |
| Stories | Approved | `units/*/stories/*.md` |
| Bolt Plan | Approved | `memory-bank/bolts/034-*` through `036-*` |

## Summary

| Metric | Count |
|--------|-------|
| Functional Requirements | 11 |
| Non-Functional Requirement Groups | 5 |
| Units | 2 |
| Stories | 7 |
| Bolts Planned | 3 |

## Decision Log

| Timestamp | Decision | Rationale | Approved |
|-----------|----------|-----------|----------|
| 2026-07-27T14:57:11Z | Booking.com is the sole authority for reservation facts and lifecycle state | Authenticated account data makes manual BookSaver CRUD duplicate and error-prone | Product owner |
| 2026-07-27T14:57:11Z | Fetch and display all reservations, including ineligible ones | Users need a complete account view and a reason when price monitoring cannot run | Product owner |
| 2026-07-27T14:57:11Z | Synchronize after connect, before checks, and for `/bookings` | User-visible and monitoring behavior must operate on current account state | Product owner |
| 2026-07-27T14:57:11Z | Retire manual registration, editing, and local deletion | Parallel mutation paths would violate the external source-of-truth model | Product owner |
| 2026-07-27T14:57:11Z | Retire guided rebooking completely | BookSaver monitors and notifies; users manage reservations directly in Booking.com | Product owner |
| 2026-07-27T14:57:11Z | Never infer or execute replacement/cancellation relationships | Similar reservations may both be legitimate and all destructive authority remains with the user | Product owner |
| 2026-07-27T16:28:04Z | Remove retired commands immediately | Compatibility aliases add no value before launch and obscure the new source of truth | Product owner |
| 2026-07-27T16:28:04Z | Destructively remove all legacy booking state | There are no active users; retaining or matching obsolete manual data adds risk without value | Product owner |

## Scope Changes

| Timestamp | Change | Reason | Impact |
|-----------|--------|--------|--------|
| 2026-07-27T14:57:11Z | Expanded GitHub issue #8 from post-connect import to continuous account synchronization | Booking.com should remain authoritative after initial discovery | Adds reconciliation and trigger integration |
| 2026-07-27T14:57:11Z | Added retirement of manual CRUD and the entire guided-rebook workflow | These flows become obsolete when account state is synchronized | Requires command, state-machine, persistence, documentation, and migration analysis |

## Ready for Construction

- [x] All requirements documented and approved.
- [x] System context defined.
- [x] Units decomposed.
- [x] Stories created and indexed.
- [x] Bolts planned.
- [x] Product owner authorized construction through final pre-merge review.

## Next Steps

Start Construction with Bolt 034, continue through verification, and stop before commit/merge for
the product owner's final approval.

## Dependencies

This intent depends on the existing encrypted per-user Booking.com session, `/connect` gateway,
serialized browser coordinator, authenticated search journey, Telegram ownership boundaries, and
savings opportunity lifecycle.
