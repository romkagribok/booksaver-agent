---
id: 002-verify-mini-app-identity
unit: 002-remote-authentication-gateway
intent: 012-per-user-booking-sessions
status: complete
priority: must
created: 2026-07-20T02:25:00.000Z
assigned_bolt: 026-remote-authentication-gateway
implemented: true
---
# Story: Verify Mini App Identity and Prevent Replay
**Global story ID**: US-090

As a user, I want the HTTPS gateway to prove that I opened my own Telegram button so that another person cannot reuse or forward access to my login browser.

## Acceptance Criteria
- [ ] Telegram `initData` HMAC, freshness, numeric user ID, and attempt binding are verified server-side.
- [ ] Attempt capabilities are single-use and exchanged for a Secure, HttpOnly, SameSite cookie.
- [ ] Stale, replayed, malformed, and cross-user requests expose no browser credentials.
