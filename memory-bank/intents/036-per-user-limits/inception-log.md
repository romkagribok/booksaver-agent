---
intent: 036-per-user-limits
created: "2026-11-10T00:46:00Z"
completed: "2026-11-10T00:46:00Z"
status: complete
---

# Inception Log: per-user-limits

## Overview

**Intent**: Per-user check limit sized for real bookings; Jev daily cap per user, not shared.
**Type**: Fix (operations)

## Decision Log

| Date | Decision | Rationale | Approved |
|------|----------|-----------|----------|
| 2026-11-10 | Production `max_checks_per_user_per_day` 12 -> 150, config only, applied 00:41Z | User 4 needs 15 a day; limit is only a loop guard | Owner: "change the checks to 150" |
| 2026-11-10 | Jev USD 0.25 daily cap becomes per user | Shared cap lets one user's loop stop all checks | Owner: "it should be per user, not shared accross all" |
| 2026-11-10 | Code default 48 -> 150 | Fresh installs match production | Engineering; reported to owner |
| 2026-11-10 | Per-stage stops waived; everything recorded | Small change | Owner chose "Record all, no stage stops" |
