---
id: US-027
status: ready
implemented: false
---

# US-027 Bring your own Anthropic API key

**Intent:** `003-telegram-interface`
**Unit:** `002-user-access-and-keys`
**Status:** Ready
**Tag:** Phase 3

## Story

**As a** guest user of a shared bot
**I want** to provide my own Anthropic API key in chat
**So that** my price checks bill my account and the owner is not paying for me

**Acceptance criteria**

- `/setkey` (or onboarding prompt) starts a key-intake dialog; the key is validated with one minimal live API call before acceptance
- The key is stored encrypted at rest (`BOOKSAVER_SECRET_KEY` env var holds the encryption key); never plaintext in DB, config, or git
- The chat message containing the key is deleted via Bot API where permitted; the key is never echoed, logged, traced, or snapshotted (extends existing redaction)
- All LLM work for my bookings (extraction + browser agent) uses my key via a per-user LLM client factory; the owner's env-var key is used only for the owner's bookings
- An invalid/revoked key fails my checks with failure code `USER_KEY_INVALID` and a bot notification telling me to `/setkey` again
- `/setkey` rotates; `/deletekey` removes the key and pauses my checks with a notice

---
