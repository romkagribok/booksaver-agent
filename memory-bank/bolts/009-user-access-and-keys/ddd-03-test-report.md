---
unit: 002-user-access-and-keys
bolt: 009-user-access-and-keys
stage: test
status: complete
updated: 2026-07-11T19:42:53Z
---

# Test Report — User Access & Keys (US-026/027/028 pass)

## Summary

- `python3 -m ruff check src/ tests/` — clean.
- `python3 -m mypy src/` — clean (strict mode, 67 source files).
- `PYTHONPATH=src python3 -m pytest` — **526 passed** (459 pre-existing + 67 new; the US-029
  pass's own report already accounted for 360 → 377 → 459 across bolts 006-009-first-pass).

## Coverage by story

### US-026 (access modes)

- `tests/unit/test_telegram_bot_config.py` — `access_mode` config parsing: defaults to `owner`,
  `invite` accepted, `open` and any other unknown value rejected at config validation (both
  through `load_config` and direct `TelegramBotSettings` construction).
- `tests/unit/telegram/test_access_control.py` — `AccessControl`: owner chat always allowed;
  `owner` mode refuses a stranger *without opening the database* (asserted via
  `not db_path.exists()`); `invite` mode admits a stranger with a valid code via `/start <code>`,
  refuses one without/with an invalid code identically, enforces single-use, rejects an expired
  code, allows an already-admitted active user on later commands, refuses a revoked one;
  `set_mode` runtime switch + rejection of an unknown mode; refusal rate-limiting.
- `tests/unit/telegram/test_gateway.py` — end-to-end through `build_bot_runner`: `invite`-mode
  stranger redemption via a real `SqliteStore`-backed invite code, owner-mode stranger refusal
  (pre-existing test, still green after the `OwnerGuard`→`AccessControl` swap).

### US-027 (hybrid billing / personal key)

- `tests/unit/test_fernet_key_store.py` — encrypt/decrypt round trip, ciphertext doesn't leak
  plaintext, missing `BOOKSAVER_SECRET_KEY` raises `SecretKeyError`, invalid (non-Fernet) key
  raises `SecretKeyError`, decrypting with the wrong key raises `SecretKeyError`, env-var
  resolution when no explicit key is passed.
- `tests/unit/telegram/test_key_dialogs.py` — `/setkey`: pending-state tracking, full round trip
  (validate → encrypt → store → delete message → confirm without echoing the key), invalid key
  rejected and not stored, key never appears in any reply text, a `delete_message` failure doesn't
  block storing the key (best-effort), `/cancelflow`-style cancel; `/deletekey`: clears a stored
  key with a reversion notice, friendly no-op when nothing was set.
- `tests/unit/test_llm_client_factory.py::TestHybridBilling` — falls back to the owner key when
  the user has none; uses the personal key when set (owner key absent entirely, proving it's
  actually the personal key in use); an undecryptable personal key raises `UserKeyInvalidError`;
  the agent-brain path also resolves the personal key; omitting `user_repo` entirely behaves like
  pre-US-027.
- `tests/unit/monitor/test_search_check_job.py::TestHybridBillingIntegration` — a per-booking
  `LLMClientFactory` that raises `UserKeyInvalidError` fails only that check with
  `FailureCode.USER_KEY_INVALID` (not a generic `EXTRACTION_FAILED`/`LLM_ERROR`); a
  non-raising factory's resolved clients are used and the check still succeeds. Confirms every
  pre-existing `llm=`/`brain=` constructor test in the same file is unaffected (`llm_factory`
  defaults to `None`).
- `tests/unit/monitor/test_trace.py::TestRedact` — a bare `sk-ant-...` key (no `key=`/`token=`
  label) is redacted; a labelled one still is too.

### US-028 (owner admin commands)

- `tests/unit/telegram/test_admin_commands.py` — non-owner refused in both `owner` and `invite`
  mode; `/admin users` lists id/telegram-id/role/access-state/key-present/booking-count;
  `/admin revoke <id>` revokes (and refuses to revoke the owner); `/admin purge <id>` requires an
  explicit `confirm` resend before deleting, then actually deletes the user; `/admin invite`
  issues a code redeemable via the real `SqliteInviteCodeRepository`; `/admin mode <mode>`
  requires `confirm`, then flips `AccessControl.mode`; unknown/missing subcommand shows usage.
- `tests/unit/telegram/test_gateway.py` — `/admin users` end-to-end as the owner; `/admin users`
  end-to-end refused for a non-owner chat (refused at the `AccessControl` layer before `/admin`'s
  own owner check even runs — same "private" refusal as any other command, which is itself a
  desirable property: a non-admitted stranger can't even discover `/admin` exists).

### Schema v8 (`invite_codes`) and repository additions

- `tests/integration/test_user_scoping.py` — `TestGetOwnerOfBooking`, `TestSetEncryptedKey`,
  `TestPurgeUser` (deletes the user and every row scoped through their bookings; owner purge
  rejected; unknown user raises), `TestInviteCodeRepository` (issue→redeem admits a user,
  double-redeem fails the second time, unknown code returns `None`, expired code can't be
  redeemed, issued codes are unique across 10 issuances).
- `tests/integration/test_check_traces.py` / `tests/integration/test_user_scoping.py` — the two
  hardcoded `SCHEMA_VERSION == 7` assertions updated to `== 8`; migration and fresh-init tests
  otherwise unchanged (v8 needed no `_migrate_v8` function — purely additive, same as v3/v4/v6).

## Gaps / deliberately out of scope for this bolt

- No live-network test hits the real Anthropic or Telegram APIs (`KeyValidator`/`TelegramBotClient`
  are always faked) — matches the "no network in tests" requirement.
- Per-user daily caps / rate limiting (FR-6, US-031) are bolt 010's `[limits]` section — not
  touched here.
- `/register` dialog and alert routing (US-025/US-030) are bolt 010 — not touched here.
