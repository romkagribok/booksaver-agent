---
unit: 001-current-rebook-opportunities
intent: 017-current-rebook-opportunities
phase: inception
status: complete
unit_type: cli
default_bolt_type: simple-construction-bolt
created: 2026-07-27T02:10:44.000Z
updated: 2026-07-27T02:10:44.000Z
---

# Unit Brief: Current Rebook Opportunities

## Purpose

Make current savings actionability explicit while keeping historical savings evidence intact.

## Scope

### In Scope

- Latest-per-active-booking SQLite selection for one user.
- Deterministic ordering and tie handling.
- Telegram picker use of current choices.
- Pre-worker and application-service freshness guards.
- Safe stale-selection guidance.
- Persistence, application, Telegram, CLI-history, and privacy regression coverage.

### Out of Scope

- Live rechecking when `/rebook` opens.
- Deleting or expiring historical positive checks.
- Changing savings notification or extraction behavior.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Select one newest opportunity per active booking | Must |
| FR-2 | Reject superseded selections at execution time | Must |
| FR-3 | Preserve audit and access boundaries | Must |

## Key Operations

| Operation | Input | Output |
|-----------|-------|--------|
| List current choices | Local user ID | One newest row per active owned booking |
| Resolve current opportunity | Booking ID | Newest opportunity or none |
| Validate selection | Opportunity ID | Current opportunity or safe stale error |
| Render picker | Current choices | One button per booking |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 3 |
| Must Have | 3 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 001-show-one-current-opportunity-per-booking | Show one current opportunity per booking | Must | Complete |
| 002-reject-superseded-rebook-selection | Reject superseded rebook selections | Must | Complete |
| 003-preserve-savings-audit-and-access-boundaries | Preserve savings audit and access boundaries | Must | Complete |

## Technical Context

Use a correlated SQLite `NOT EXISTS` query keyed by `(validated_at, id)` to avoid window-function
version assumptions and select current rows in one query. Add a repository current-row lookup and
enforce it in the shared application service; Telegram performs an earlier UX-oriented guard.

## Success Criteria

- [x] `/rebook` shows one newest opportunity for each active owned booking.
- [x] Historical or stale buttons cannot create a session or prompt.
- [x] Distinct bookings remain distinct choices in newest-first order.
- [x] Archived and foreign bookings remain hidden.
- [x] Historical savings and CLI diagnostics remain intact.
- [x] Focused and full quality gates pass.
- [ ] Final product-owner merge review is complete.

## Bolt Suggestion

`032-current-rebook-opportunities` — Simple Construction, all three stories.
