---
id: 004-inspect-session-health-safely
unit: 001-per-user-booking-sessions
intent: 012-per-user-booking-sessions
status: complete
priority: must
created: 2026-07-19T21:23:00.000Z
assigned_bolt: 024-per-user-booking-sessions
implemented: true
---
# Story: Inspect Session Health Safely
**Global story ID**: US-080

As a user/operator, I want redacted session health so that I know when a re-import is required without disclosing secrets.

## Acceptance Criteria
- [ ] Status distinguishes missing, ready, expired, reauth-required, and invalid.
- [ ] Users see only their state; aggregate admin output reveals no account/cookie details.
- [ ] Guidance contains the scoped CLI re-import command.
