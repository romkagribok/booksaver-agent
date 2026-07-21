---
id: 002-import-user-session-securely
unit: 001-per-user-booking-sessions
intent: 012-per-user-booking-sessions
status: complete
priority: must
created: 2026-07-19T21:23:00.000Z
assigned_bolt: 024-per-user-booking-sessions
implemented: true
---
# Story: Import a User Session Securely
**Global story ID**: US-078

As the VPS operator, I want to import cookies for one admitted Telegram user over SSH so that authenticated checks work without sending secrets to the bot.

## Acceptance Criteria
- [ ] CLI requires an explicit admitted Telegram user target.
- [ ] Invalid/expired/non-Booking.com input changes nothing and reveals no cookie values.
- [ ] Runbook uses SCP/SSH, immediate source deletion, and no Telegram upload.
