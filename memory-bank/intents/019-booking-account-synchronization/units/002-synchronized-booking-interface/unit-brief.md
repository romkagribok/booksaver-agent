---
unit: 002-synchronized-booking-interface
intent: 019-booking-account-synchronization
phase: inception
status: complete
unit_type: cli
default_bolt_type: ddd-construction-bolt
created: 2026-07-27T16:28:04.000Z
updated: 2026-07-27T16:28:04.000Z
---

# Unit Brief: Synchronized Booking Interface

## Purpose

Make synchronized Booking.com inventory the only user-facing booking model and remove every manual
booking mutation or guided-rebook path.

## Scope

### In Scope

- Synchronization after session intake, before checks, and for `/bookings`.
- Caller-visible full inventory, freshness, lifecycle, and eligibility reasons.
- Immediate command/catalog/callback/dialog retirement.
- Removal of normal CLI booking mutation and new rebook-session creation.
- Documentation and operator guidance for the new monitor-and-notify product boundary.

### Out of Scope

- Inventory extraction and persistence internals owned by Unit 1.
- Any reservation mutation, replacement inference, or legacy compatibility alias.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-4 | Synchronize at every approved freshness boundary | Must |
| FR-7 | Make `/bookings` the synchronized reservation-status experience | Must |
| FR-8 | Retire manual booking mutation paths | Must |
| FR-9 | Retire guided rebooking while preserving useful savings | Must |

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
| US-116 | Synchronize at every freshness boundary | Must | Ready |
| US-117 | Show every reservation and eligibility reason | Must | Ready |
| US-118 | Remove manual booking mutation and guided rebooking | Must | Ready |

## Dependencies

- `001-booking-account-sync-core` and Bolts 034–035.
- Existing Telegram gateway, scheduler/check coordinator, command catalog, `/connect`, `/checknow`,
  notification adapters, and current-savings queries.

## Success Criteria

- [ ] Every approved trigger requires a conclusive caller-scoped synchronization.
- [ ] `/bookings` shows all synchronized reservations and precise reasons without mutation actions.
- [ ] Retired commands are absent and immediately unknown.
- [ ] Savings remain informational; no guided rebook session can start.
- [ ] Existing access/revocation/resource controls remain intact.
- [ ] Documentation and full quality gates pass.

## Bolt Suggestion

- `036-synchronized-booking-interface`: trigger integration, Telegram/CLI retirement, UI, and docs.
