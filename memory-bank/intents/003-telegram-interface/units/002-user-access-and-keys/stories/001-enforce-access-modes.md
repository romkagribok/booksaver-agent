---
id: 001-enforce-access-modes
status: complete
implemented: true
---

# US-026 Enforce access modes for a discoverable bot

**Intent:** `003-telegram-interface`
**Unit:** `002-user-access-and-keys`
**Status:** Complete
**Tag:** Phase 3

## Story

**As the** bot owner
**I want** configurable access modes (`owner`, `invite`)
**So that** a stranger who discovers the bot can never spend my money or read anyone's data

> Checkpoint 1 (2026-07-11): the previously drafted `open` mode is **cut from scope** — operating a
> publicly available bot would make the owner the operator of a third-party scraping service (ToS
> exposure) and concentrate all traffic on one IP. Strangers self-host the open-source repo instead.

**Acceptance criteria**

- Given mode `owner`: only allowlisted Telegram user IDs get past `/start`; others get one polite refusal and are rate-limited
- Given mode `invite`: a valid single-use invite code (issued by owner) admits a new user; anyone without one is refused identically to `owner` mode
- Identity comes from Telegram update metadata (user ID), never message content
- Mode is config-validated at load; default is `owner`; unknown modes (including `open`) are rejected at config validation
- Refused interactions are logged (user ID, command) without message bodies

---
