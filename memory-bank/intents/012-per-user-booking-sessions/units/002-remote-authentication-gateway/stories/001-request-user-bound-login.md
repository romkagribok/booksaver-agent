---
id: 001-request-user-bound-login
unit: 002-remote-authentication-gateway
intent: 012-per-user-booking-sessions
status: complete
priority: must
created: 2026-07-20T02:25:00.000Z
assigned_bolt: 026-remote-authentication-gateway
implemented: true
---
# Story: Request a User-Bound Login
**Global story ID**: US-089

As an admitted Telegram user, I want `/connect` to give me a short-lived login button so that I can establish my own Booking.com session from my phone.

## Acceptance Criteria
- [ ] The command is caller-scoped and private-chat-only through existing admission controls.
- [ ] The attempt uses opaque random identifiers, a bounded lifetime, and one active browser globally.
- [ ] Busy, disabled, and setup-failure responses are immediate and actionable.
