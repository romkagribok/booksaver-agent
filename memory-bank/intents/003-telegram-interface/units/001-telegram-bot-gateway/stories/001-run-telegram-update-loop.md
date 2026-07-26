---
id: 001-run-telegram-update-loop
status: complete
implemented: true
---

# US-023 Run Telegram update loop inside the daemon

**Intent:** `003-telegram-interface`
**Unit:** `001-telegram-bot-gateway`
**Status:** Complete
**Tag:** Phase 3

## Story

**As a** bot user
**I want** the daemon to receive my Telegram messages continuously
**So that** I can interact with BookSaver without touching the machine it runs on

**Acceptance criteria**

- Given the daemon starts with `[telegram_bot]` configured (token env var `BOOKSAVER_TELEGRAM_BOT_TOKEN`)
- When it runs
- Then a long-polling thread calls `getUpdates` (stdlib urllib + certifi, 25–50 s poll timeout) beside the scheduler in the same process
- And a slow or failed price check never delays bot replies
- Given the daemon restarts
- Then the persisted update offset ensures no command is lost or processed twice
- And stopping the daemon stops the bot thread cleanly (no orphan poll)
- Given `[telegram_bot]` is absent, the daemon runs exactly as today (laptop mode unaffected)

---
