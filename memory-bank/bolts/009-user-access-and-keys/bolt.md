---
id: 009-user-access-and-keys
unit: 002-user-access-and-keys
intent: 003-telegram-interface
type: ddd-construction-bolt
status: complete
stories:
  - 001-enforce-access-modes
  - 002-bring-your-own-anthropic-key
  - 003-owner-admin-commands
  - 004-user-scoped-persistence
created: 2026-07-11T17:39:20Z
started: 2026-07-11T17:39:20Z
completed: 2026-07-11T19:42:53Z
current_stage: test
stages_completed:
  - name: model
    completed: 2026-07-11T17:50:00Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-11T17:52:00Z
    artifact: ddd-02-technical-design.md
  - name: implement (US-029 slice)
    completed: 2026-07-11T17:57:19Z
    artifact: domain/user.py + schema v7 migration + SqliteUserRepository +
      BookingRepository/SavingsRepository scoping + LLMClientFactory seam
  - name: implement (US-026/027/028 slice)
    completed: 2026-07-11T19:42:53Z
    artifact: infrastructure/telegram/access.py (AccessControl),
      infrastructure/persistence/schema.sql (v8 invite_codes),
      infrastructure/crypto/fernet_key_store.py, infrastructure/telegram/key_validator.py,
      infrastructure/telegram/key_dialogs.py, infrastructure/telegram/admin_commands.py,
      infrastructure/llm/client_factory.py (hybrid resolution), gateway.py wiring
  - name: test
    completed: 2026-07-11T19:42:53Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 008-telegram-bot-gateway
enables_bolts:
  - 010-conversational-booking-ops
requires_units: []
blocks: false
complexity:
  avg_complexity: 4
  avg_uncertainty: 3
  max_dependencies: 2
  testing_scope: 4
---

# Bolt: 009-user-access-and-keys

## Overview

Second bolt of intent 003. Turns the single-user daemon into a small self-hosted multi-user
service: schema v7 `users` table + user-scoped repositories, access modes (`owner`/`invite`),
hybrid LLM billing (owner key + per-user caps by default, optional encrypted personal key), and
owner admin commands.

**This bolt record covers the full unit's stories, built in two passes.** The first pass shipped
US-029 (schema v7 multi-user foundation). This second pass completes the unit: US-026 (access
modes + real `AccessControl`), US-027 (hybrid billing, `/setkey`/`/deletekey`, Fernet key
encryption), and US-028 (owner admin commands) are now implemented and tested — the unit is
complete.

## Objective

A multi-user-capable persistence foundation exists: every booking (and everything that inherits
scope through it — checks, savings, rebook sessions, traces) is tied to an owning user, migration
from the pre-v7 single-user schema is lossless and assigns existing data to the owner, and a
laptop (single-owner) deployment is provably unchanged in behavior. On top of that foundation, a
discoverable Telegram bot is now safe to run: strangers get one refusal and can trigger nothing;
invited users bill the owner's key by default and may opt into an encrypted personal key; the
owner can list/revoke/purge users, issue invite codes, and switch access mode from chat.

## Stories Included (this bolt)

- **US-026**: Enforce access modes for a discoverable bot (Must) — **implemented**
- **US-027**: Bring your own Anthropic key (Must) — **implemented**
- **US-028**: Owner admin commands (Must) — **implemented**
- **US-029**: User-scoped persistence, schema v7 (Must) — **implemented** (first pass)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ✅ **1. Domain Model**: Complete (full unit scope) → ddd-01-domain-model.md
- ✅ **2. Technical Design**: Complete (full unit scope) → ddd-02-technical-design.md
- ✅ **3. Implement**: All four stories complete
- ✅ **4. Test**: Full-unit test report → ddd-03-test-report.md (526 tests total, all green)

## Dependencies

### Requires
- Bolt 008 (telegram-bot-gateway) — router/dialog machine that US-026/027/028 hook into
  (not required for the US-029 persistence slice, which has no Telegram surface)
- intent-001 unit 001 (core-local-data) — SQLite migration framework (v6 → v7)
- intent-002 units — `LLMExtractor`/`AgentBrain` construction seam replaced by
  `LLMClientFactory`

### Enables
- Bolt 010 (conversational-booking-ops) — per-user registration/alert routing
- The rest of this bolt (US-026/027/028) — schema v7 is their foundation

## Success Criteria (US-029 slice)

- [x] Schema v7 adds `users` (exactly one `owner` row, enforced by a partial unique index) and
  `bookings.user_id` (NOT NULL FK, backfilled to the owner on migration)
- [x] A v6 database with existing bookings/checks/savings migrates so every booking belongs to
  the owner; a fresh init creates v7 directly with the owner already present
- [x] Laptop single-user mode (one user = the owner) behaves identically after migration
- [x] Repository APIs offer user-scoped listing methods (`list_active_for_user`,
  `list_all_for_user`, `SavingsRepository.list_all_for_user`); integration tests prove two users'
  bookings/savings never cross-leak
- [x] CLI commands (`register`, `bookings list`, `savings list`) resolve and operate as the owner
  user; behavior/output unchanged for a laptop deployment
- [x] `LLMClientFactory` seam introduced (`for_booking` / `agent_brain_for_booking`); check path
  goes through it; behavior unchanged (owner env-var key or DOM/scripted-only degradation)

## Success Criteria (US-026/027/028 slice)

- [x] `[telegram_bot].access_mode` (`owner`|`invite`, default `owner`) validated at config load;
  `open`/unknown values rejected with a clear message
- [x] Real `AccessControl` resolves every update via `UserRepository`; owner chat id always
  allowed; `owner` mode refuses everyone else; `invite` mode admits a known active user, refuses a
  revoked one, and lets a stranger redeem a single-use invite code via `/start <code>` (identical
  refusal for "no code"/"wrong code"/"invite mode off")
- [x] Schema v8: `invite_codes` table (single-use, owner-issued, optional expiry), purely additive
- [x] `cryptography` (Fernet) added as an approved runtime dependency; `FernetKeyStore` encrypts/
  decrypts with `BOOKSAVER_SECRET_KEY`, raising a clear operator-facing `SecretKeyError` when
  missing/invalid — owner-billed checks never touch this path
- [x] `/setkey` validates with one live Anthropic call (`KeyValidator` seam, faked in tests),
  encrypts, stores, deletes the chat message (best-effort), never echoes the key; `/deletekey`
  clears it and reverts to owner-billed
- [x] Trace/snapshot redaction extended to catch bare `sk-ant-...` key material, not just
  labelled `key=`/`token=` text
- [x] `AnthropicLLMClientFactory` resolves booking → owning user → personal key (decrypt) →
  fallback to owner key; an undecryptable personal key raises `UserKeyInvalidError`, mapped to
  `FailureCode.USER_KEY_INVALID` in `BookingComSearchMonitor._run_check_inner` (additive
  `llm_factory` param; every existing constructor-injected-`llm`/`brain` call site/test unaffected)
- [x] `/admin users|revoke|purge|invite|mode` — owner-only (re-checked per branch), purge/mode
  require an explicit `confirm` resend, all refusals logged (user id + command only)

## Notes

- `BookingRepository.get_by_id` / `get_by_confirmation` / `set_occupancy` remain unscoped
  (looked up by an already-known, unguessable UUID/confirmation id from a trusted call site) —
  only the "list all" style reads that are actually exposed as owner-facing listings were scoped
  this pass. Documented as a known follow-up in ddd-02 if a stronger per-request scoping bound is
  needed once the bot gateway exposes untrusted routing.
- `/setkey` is deliberately not built on the shared `DialogManager`/`DialogDefinition` framework
  (see ddd-02) — its `on_complete` hook doesn't receive the raw Telegram `message_id`, which is
  needed to delete the chat message containing the pasted key. A small dedicated `KeyIntakeFlow`
  tracks pending chats instead.
- `IncomingCommand` gained a `message_id: int = 0` field (default keeps every pre-existing
  construction site working); `BotLoop`'s `access_guard`/`on_refused` now receive the whole
  `IncomingCommand` instead of a bare `chat_id`, because `invite` mode's `/start <code>` admission
  path needs the command and args, not just the chat id.
- Schema bumped to **v8** (`invite_codes`, purely additive — no table rebuild, following the same
  pattern as v3/v4/v6). Bolt 010 (running in parallel) was told not to touch schema; flagged in
  the final report for the orchestrator to reconcile if both passes land.
