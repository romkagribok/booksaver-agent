---
id: 006-preserve-session-safety-and-lifecycle
unit: 001-per-user-booking-sessions
intent: 012-per-user-booking-sessions
status: complete
priority: must
created: 2026-07-19T21:23:00.000Z
assigned_bolt: 024-per-user-booking-sessions
implemented: true
---
# Story: Preserve Session Safety and Lifecycle
**Global story ID**: US-082

As a user, I want session refresh, replacement, deletion, and revocation to remain safe while final booking actions stay human-only.

## Acceptance Criteria
- [ ] Revocation blocks resolution/refresh; deletion affects only the target user.
- [ ] Refreshed state replaces only the still-current revision.
- [ ] Browser guards continue denying reserve, checkout, payment, and cancel actions.
