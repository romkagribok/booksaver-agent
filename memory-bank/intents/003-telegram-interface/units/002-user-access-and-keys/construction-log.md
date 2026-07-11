# Construction Log: User Access & Keys

**Unit:** `002-user-access-and-keys`
**Intent:** `003-telegram-interface`

## 2026-07-11T17:57:19Z — Bolt 009 (US-029 slice)

**Story completed: US-029 — User-scoped persistence (schema v7)**

Implemented the multi-user persistence foundation for the unit:

- `src/booksaver/domain/user.py` — `User`, `UserRole`, `UserAccessState`.
- Schema v7 (`SCHEMA_VERSION = 7`): `users` table with a partial unique index guaranteeing
  exactly one `owner` row, and `bookings.user_id` (`NOT NULL REFERENCES users`). `_migrate_v7`
  rebuilds `bookings` the same way `_migrate_v5` rebuilt `check_history` (SQLite can't add a
  constrained FK column to a populated table in place); `_ensure_owner_user` is called both from
  the migration and unconditionally after `schema.sql` runs, so a fresh init also gets an owner
  with no migration code path involved.
- `SqliteUserRepository`: `get_owner`, `get_by_id`, `get_by_telegram_id`,
  `get_or_create_by_telegram_id`, `list_all`, `list_active`, `set_access_state`.
- `BookingRepository.add(booking, user_id=None)` (defaults to the owner — every pre-existing
  single-owner call site is unaffected) + `list_active_for_user`/`list_all_for_user`.
  `SavingsRepository.list_all_for_user` (JOIN through `bookings.user_id`).
- `LLMClientFactory` port + `AnthropicLLMClientFactory`: `for_booking`/`agent_brain_for_booking`
  replace `cli/commands.py`'s inline `_make_llm_extractor`/`_make_agent_brain` bodies (those two
  functions are now thin wrappers). Behavior is byte-identical to pre-v7 (owner env-var key,
  DOM-only/scripted-only degradation on a missing key).
- CLI: `cmd_register`, `cmd_bookings_list`, `cmd_savings_list` resolve the owner user and pass
  its id through to the scoped repository methods.

**Deliberately deferred to a later pass of bolt 009**: US-026 (access modes + router guard),
US-027 (hybrid billing + `/setkey` + key encryption), US-028 (owner admin commands). Those
stories remain `status: ready` in their story files.

**Tests**: `tests/integration/test_user_scoping.py` (v6→v7 migration incl. idempotency and fresh
init, exactly-one-owner DB invariant, `UserRepository` behavior, cross-user isolation for
bookings and savings) and `tests/unit/test_llm_client_factory.py` (factory seam). Full suite:
377 passed (360 pre-existing + 17 new), `ruff check src/` clean, `mypy src/` clean.

**Files touched outside the unit's own new files**: `application/ports.py`,
`application/register_booking.py`, `cli/commands.py`, `infrastructure/persistence/schema.sql`,
`infrastructure/persistence/sqlite_store.py`, plus three test fixture files
(`tests/unit/monitor/fakes.py`, `tests/unit/savings/test_pipeline.py`,
`tests/unit/rebook/test_rebook_service.py`) that needed the new protocol methods added to their
fakes for structural (mypy) conformance.

## 2026-07-11T19:42:53Z — Bolt 009 (US-026/027/028 slice — unit complete)

**Stories completed: US-026 (access modes), US-027 (hybrid billing / personal key), US-028
(owner admin commands)**

Completed the unit. First, `git merge phase-3-telegram-interface` (commit 98a0094, "Wave 1")
brought in the telegram gateway package/schema v7/deployment artifacts this pass builds on.

- **US-026**: `infrastructure/telegram/access.py::AccessControl` — real multi-user access
  control (owner-chat fast-path never touches the DB; `owner` mode refuses everyone else without
  a DB query either; `invite` mode resolves via `UserRepository`, admits a stranger only through
  `/start <code>` against a valid single-use `invite_codes` row). `[telegram_bot].access_mode`
  (`owner`|`invite`, default `owner`) added to `TelegramBotSettings` + `load_config.py`; `open`/
  unknown values rejected at config validation. Schema **v8**: `invite_codes` table (purely
  additive, no rebuild — same pattern as v3/v4/v6), `SqliteInviteCodeRepository`
  (`issue`/`redeem`/`get`). `IncomingCommand` gained `message_id: int = 0`; `BotLoop`'s
  `access_guard`/`on_refused` now take the whole `IncomingCommand` (invite-mode admission needs
  the command/args, not just chat id) — command parsing moved earlier in `_dispatch` accordingly.
  Refusals logged (user id + command only, per US-026 AC).
- **US-027**: `infrastructure/crypto/fernet_key_store.py::FernetKeyStore` (lazy
  `BOOKSAVER_SECRET_KEY` read; `SecretKeyError` only on an actual encrypt/decrypt attempt —
  owner-only deployments are unaffected). `infrastructure/telegram/key_validator.py`
  (`KeyValidator` protocol + `AnthropicKeyValidator`, one live `models.list(limit=1)` call).
  `infrastructure/telegram/key_dialogs.py::KeyIntakeFlow` (`/setkey`, deliberately not built on
  the shared `DialogManager` — see ddd-02) + `handle_deletekey` (`/deletekey`).
  `SqliteUserRepository.set_encrypted_key`/`get_owner_of_booking` added.
  `AnthropicLLMClientFactory` extended with `user_repo`/`key_store`: resolves booking → owning
  user → decrypted personal key, else owner key; raises `UserKeyInvalidError` on an
  undecryptable stored key. `BookingComSearchMonitor` gained an additive `llm_factory` param —
  when set, re-resolves `self._llm`/`self._brain` per booking in `_run_check_inner`, mapping
  `UserKeyInvalidError` to the new `FailureCode.USER_KEY_INVALID`. `cli/commands.py`'s `_job()`
  now builds the factory per tick (with `user_repo`/`key_store` wired) instead of pre-resolving
  `llm`/`brain` once, and a new `_notify_invalid_user_keys` sends a direct Telegram DM
  (best-effort) to a user whose personal key just failed. `monitor/trace.py::redact` extended
  with an unconditional `sk-ant-...` pattern (personal keys are shaped distinctively, not just
  labelled `key=`). New runtime dep `cryptography>=42` (ADR-019).
- **US-028**: `infrastructure/telegram/admin_commands.py::register_admin_commands` —
  `/admin users|revoke|purge|invite|mode`, every branch independently re-checking
  `access_control.is_owner`; `purge`/`mode` require an explicit `... confirm` resend (no
  inline-keyboard confirmation needed — that's bolt 011's rebook-gate concern).
  `SqliteUserRepository.purge` added (deletes a non-owner user and everything scoped through
  their bookings; owner purge rejected; unknown user raises `KeyError`).
- `infrastructure/telegram/gateway.py` — `OwnerGuard` swapped for `AccessControl`; new commands
  registered in a clearly-delimited block (coordination note: bolt 010 registers its own commands
  in the same file, additively).

**Tests**: 67 new tests across `tests/unit/test_fernet_key_store.py`,
`tests/unit/telegram/test_access_control.py`, `tests/unit/telegram/test_key_dialogs.py`,
`tests/unit/telegram/test_admin_commands.py`, extensions to
`tests/unit/test_llm_client_factory.py` (`TestHybridBilling`),
`tests/unit/monitor/test_search_check_job.py` (`TestHybridBillingIntegration`),
`tests/unit/monitor/test_trace.py` (bare-key redaction), `tests/integration/test_user_scoping.py`
(`TestGetOwnerOfBooking`, `TestSetEncryptedKey`, `TestPurgeUser`, `TestInviteCodeRepository`),
and `tests/unit/telegram/test_gateway.py` (end-to-end `/admin`, invite-mode `/start <code>`).
Full suite: **526 passed** (459 pre-existing + 67 new), `ruff check src/ tests/` clean,
`mypy src/` clean (strict).

**Unit `002-user-access-and-keys` is now complete** — all four stories (US-026/027/028/029)
implemented and tested.

**Coordination note for the orchestrator**: this pass bumped `SCHEMA_VERSION` to **8**
(`invite_codes`, purely additive) — flagged per the coordination instructions since bolt 010
(running in parallel) was told not to touch schema.
