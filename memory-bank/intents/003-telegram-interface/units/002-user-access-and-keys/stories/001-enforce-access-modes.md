---
id: US-026
status: ready
implemented: false
---

# US-026 Enforce access modes for a discoverable bot

**Intent:** `003-telegram-interface`
**Unit:** `002-user-access-and-keys`
**Status:** Ready
**Tag:** Phase 3

## Story

**As the** bot owner
**I want** configurable access modes (`owner`, `invite`, `open`)
**So that** a stranger who discovers the bot can never spend my money or read anyone's data

**Acceptance criteria**

- Given mode `owner`: only allowlisted Telegram user IDs get past `/start`; others get one polite refusal and are rate-limited
- Given mode `invite`: a valid single-use invite code (issued by owner) admits a new user
- Given mode `open`: anyone may `/start` and `/setkey`, but every stateful or LLM-consuming feature is locked until a valid personal key is stored (US-027)
- Identity comes from Telegram update metadata (user ID), never message content
- Mode is config-validated at load; default is `owner`
- Refused interactions are logged (user ID, command) without message bodies

---
