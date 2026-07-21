---
id: 001-isolate-booking-sessions-by-user
unit: 001-per-user-booking-sessions
intent: 012-per-user-booking-sessions
status: complete
priority: must
created: 2026-07-19T21:23:00.000Z
assigned_bolt: 024-per-user-booking-sessions
implemented: true
---
# Story: Isolate Booking.com Sessions by User
**Global story ID**: US-077

As a Telegram user, I want my checks to use only my Booking.com session so that another account's eligibility or secrets cannot affect my results.

## Acceptance Criteria
- [ ] Session lookup is keyed by stable local user ID resolved from booking ownership.
- [ ] Every restored state enters a fresh/clean browser context.
- [ ] Owner, invitee, revoked, and sequential-user tests prove no fallback or bleed.
