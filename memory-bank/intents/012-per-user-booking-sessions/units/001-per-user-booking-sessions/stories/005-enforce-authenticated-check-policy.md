---
id: 005-enforce-authenticated-check-policy
unit: 001-per-user-booking-sessions
intent: 012-per-user-booking-sessions
status: complete
priority: must
created: 2026-07-19T21:23:00.000Z
assigned_bolt: 024-per-user-booking-sessions
implemented: true
---
# Story: Enforce Authenticated Check Policy
**Global story ID**: US-081

As a user monitoring Genius prices, I want checks to fail explicitly when my login is unavailable so that a public result cannot hide a saving.

## Acceptance Criteria
- [ ] All Telegram-owned scheduled/on-demand checks require the owner's valid session.
- [ ] Auth failure records no price/opportunity and does not affect another user.
- [ ] Refresh/invalidation uses session revisions to avoid stale overwrite.
