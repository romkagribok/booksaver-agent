---
id: 005-report-and-reconnect
unit: 002-remote-authentication-gateway
intent: 012-per-user-booking-sessions
status: complete
priority: must
created: 2026-07-20T02:25:00.000Z
assigned_bolt: 026-remote-authentication-gateway
implemented: true
---
# Story: Report Outcomes and Request Reconnect
**Global story ID**: US-093

As a user, I want explicit connection outcomes and bounded reconnect prompts so that expired authentication never silently disables savings checks.

## Acceptance Criteria
- [ ] Telegram proactively reports success, timeout, cancellation, and redacted failure.
- [ ] Scheduled auth failures produce one reconnect prompt per health transition/cooldown.
- [ ] Messages contain no cookies, account data, passwords, VNC credentials, or raw exceptions.
