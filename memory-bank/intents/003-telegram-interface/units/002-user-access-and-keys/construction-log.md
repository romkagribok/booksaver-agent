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
