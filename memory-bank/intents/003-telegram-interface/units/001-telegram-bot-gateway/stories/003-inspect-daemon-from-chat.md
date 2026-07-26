---
id: 003-inspect-daemon-from-chat
status: complete
implemented: true
---

# US-036 Inspect daemon health and history from chat

**Intent:** `003-telegram-interface`
**Unit:** `001-telegram-bot-gateway`
**Status:** Complete
**Tag:** Phase 3

## Story

**As a** user
**I want** `/status`, `/bookings`, `/savings`, and `/checks` in Telegram
**So that** I can see what the monitor is doing without SSH or CLI access

**Acceptance criteria**

- `/status` shows daemon uptime, bookings monitored, last check outcome per booking, next scheduled run
- `/bookings` mirrors `bookings list` (scoped to me once Unit 2 lands; owner-only until then)
- `/savings` lists detected opportunities with amounts and detected-at timestamps
- `/checks <booking>` shows recent check history with failure codes; long traces are summarized, not dumped
- All read-only commands respond in ≤ 3 s while a check is running
- Until Unit 2 lands, all commands refuse chats other than the configured owner chat ID

---
