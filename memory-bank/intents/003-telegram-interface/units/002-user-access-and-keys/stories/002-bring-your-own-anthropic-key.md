---
id: 002-bring-your-own-anthropic-key
status: complete
implemented: true
---

# US-027 Optional personal Anthropic API key (hybrid billing)

**Intent:** `003-telegram-interface`
**Unit:** `002-user-access-and-keys`
**Status:** Complete
**Tag:** Phase 3

## Story

**As an** invited user of a shared bot
**I want** the option to provide my own Anthropic API key in chat
**So that** my price checks can bill my account instead of the owner's

> Checkpoint 1 (2026-07-11): billing is **hybrid** — invited users run on the owner's key under
> per-user daily caps by default; a personal key is optional, not a gate on any feature.

**Acceptance criteria**

- Without a personal key, all LLM work for my bookings uses the owner's env-var key, bounded by per-user daily caps (US-031)
- `/setkey` starts a key-intake dialog; the key is validated with one minimal live API call before acceptance
- The key is stored encrypted at rest (Fernet via `cryptography`; `BOOKSAVER_SECRET_KEY` env var holds the encryption key); never plaintext in DB, config, or git
- The chat message containing the key is deleted via Bot API where permitted; the key is never echoed, logged, traced, or snapshotted (extends existing redaction)
- Once stored, all LLM work for my bookings (extraction + browser agent) uses my key via the per-user LLM client factory
- An invalid/revoked personal key fails my checks with failure code `USER_KEY_INVALID` and a bot notification telling me to `/setkey` again or `/deletekey` to revert to owner-billed
- `/setkey` rotates; `/deletekey` removes the key and reverts me to owner-billed checks with a notice

---
