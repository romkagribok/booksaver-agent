---
id: 003-operate-transient-remote-browser
unit: 002-remote-authentication-gateway
intent: 012-per-user-booking-sessions
status: complete
priority: must
created: 2026-07-20T02:25:00.000Z
assigned_bolt: 026-remote-authentication-gateway
implemented: true
---
# Story: Operate a Transient Remote Mobile Browser
**Global story ID**: US-091

As a phone user, I want to interact with the real Booking.com login page in a temporary mobile browser so that password and MFA entry never occur in bot messages.

## Acceptance Criteria
- [ ] Playwright launches headed Chromium with the configured mobile profile on a fresh virtual display.
- [ ] noVNC/websockify stream only the display through a token-gated WSS path behind Caddy.
- [ ] Login screenshots, traces, recordings, LLM observation, and unrestricted top-level navigation are disabled.
