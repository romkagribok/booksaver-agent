---
id: 004-preserve-audit-and-invalidate-stale-savings
unit: 001-post-rebook-monitoring
intent: 011-post-rebook-monitoring
status: complete
priority: must
created: 2026-07-19T19:50:29.000Z
assigned_bolt: 023-post-rebook-monitoring
implemented: true
---

# Story: Preserve Audit and Invalidate Stale Savings

**Global story ID**: US-075

## User Story

**As the** BookSaver operator
**I want** reconciliation to retain evidence but remove obsolete actions
**So that** history remains explainable and stale savings cannot be rebooked

## Acceptance Criteria

- [ ] Replacement propagation and cancellation-only archive remove all old savings opportunities.
- [ ] Check history, traces, sessions, and events remain linked to the stable booking.
- [ ] The monitoring disposition event commits atomically with booking/savings state.
- [ ] Audit detail excludes tracking/session query parameters and Telegram message bodies.

## Dependencies

- US-073 atomic propagation and US-074 outcome matrix.
