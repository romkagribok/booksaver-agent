---
intent: 017-current-rebook-opportunities
created: 2026-07-27T02:10:44Z
completed: 2026-07-27T02:10:44Z
status: complete
---

# Inception Log: Current Rebook Opportunities

## Overview

**Intent**: Remove duplicate historical `/rebook` choices and prevent superseded selections.
**Type**: Brown-field Telegram bug fix and savings-lifecycle correction.

## Artifacts Created

| Artifact | Status | File |
|----------|--------|------|
| Requirements | Approved | `requirements.md` |
| System Context | Approved | `system-context.md` |
| Units | Approved | `units.md` |
| Stories | Approved | `units/001-current-rebook-opportunities/stories/*.md` |
| Bolt Plan | Approved | `memory-bank/bolts/032-current-rebook-opportunities/` |

## Summary

| Metric | Count |
|--------|-------|
| Functional Requirements | 3 |
| Non-Functional Requirement Groups | 4 |
| Units | 1 |
| Stories | 3 |
| Bolts Planned | 1 |

## Decision Log

| Timestamp | Decision | Rationale | Approved |
|-----------|----------|-----------|----------|
| 2026-07-27T02:10:44Z | Show one newest opportunity per active booking | Repeated checks should not create contradictory choices for one reservation | Product owner |
| 2026-07-27T02:10:44Z | Preserve historical savings rows | Audit history remains useful and existing lifecycle cleanup already handles replaced/deleted bookings | Product owner |
| 2026-07-27T02:10:44Z | Revalidate before session creation | An old Telegram message or manual ID must not bypass the picker policy | Product owner |
| 2026-07-27T02:10:44Z | Do not trigger a live price check from `/rebook` | This intent corrects selection semantics without adding Booking.com latency or browser contention | Product boundary |

## Ready for Construction

- [x] All requirements documented.
- [x] System context defined.
- [x] Unit decomposed.
- [x] Stories created and indexed.
- [x] Bolt 032 planned.
- [x] Product-owner direction authorizes construction through final pre-merge review.

## Next Steps

Route Bolt 032 to the Construction Agent's Plan stage.
