---
id: 001-discover-and-select-immediate-check
unit: 001-on-demand-check-orchestration
intent: 007-telegram-on-demand-checks
status: complete
priority: must
created: 2026-07-18T23:40:00Z
assigned_bolt: 019-on-demand-check-orchestration
implemented: true
---

# Story: Discover and Select an Immediate Check

**Global story ID**: US-052

## User Story

**As an** authorized Telegram user
**I want** to select one of my bookings from `/checknow`
**So that** I can request a live price without copying a UUID

## Acceptance Criteria

- [x] The command is present in the catalog, help/welcome text, and native menus.
- [x] No argument renders only caller-owned active bookings as buttons.
- [x] Exact IDs and unique caller-scoped prefixes of at least eight characters work.
- [x] Invalid, ambiguous, stale, inactive, or foreign selectors are non-disclosing.

## Dependencies

- US-043–US-045 interactive command navigation; US-049 owner-scoped booking resolution.
