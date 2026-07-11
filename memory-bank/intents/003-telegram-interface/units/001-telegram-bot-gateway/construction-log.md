# Construction Log: Telegram Bot Gateway

**Intent:** `003-telegram-interface`
**Unit:** `001-telegram-bot-gateway`
**Status:** Complete

## Bolt 008 — 2026-07-11T17:39:20Z → 2026-07-11T18:20:00Z

Delivered US-023 (update loop + offset durability + fail-fast watchdog), US-024 (command
router + conversation-state-machine framework + `/cancelflow`), and US-036 (read-only
`/status`, `/bookings`, `/savings`, `/checks` commands).

- **Stages**: model → design → ADR-018 → implement → test, all complete (see
  `memory-bank/bolts/008-telegram-bot-gateway/`).
- **Result**: 434/434 tests passing (74 new), ruff clean, mypy clean.
- **New package**: `src/booksaver/infrastructure/telegram/` (`client`, `offset_store`,
  `router`, `dialogs`, `access`, `commands_readonly`, `bot_loop`, `gateway`).
- **Changed**: `daemon/scheduler.py` (+`stop_event`/`started_at`/`next_run_at`),
  `daemon/lifecycle.py` (threaded scheduler + optional bot thread + watchdog),
  `domain/value_objects.py` (+`TelegramBotSettings`), `domain/models.py`
  (`Config.telegram_bot_settings`), `application/load_config.py` (`[telegram_bot]`
  parsing), `cli/commands.py` (`cmd_run` wiring, config template, `config show`).
- **Not touched** (coordination with parallel bolts 009/012 workers): schema/`sqlite_store.py`,
  `_make_llm_extractor`/`_make_agent_brain`, `monitor/session_manager.py`, deployment files.

Completion criteria met: daemon runs scheduler + bot loop in one process and both stop
cleanly on SIGTERM/SIGINT; owner commands work while a check is in progress; non-owner
chats get exactly one refusal and are then rate-limited with no state/LLM effect; the
Telegram offset survives a restart with neither drops nor replays; `[telegram_bot]` absent
leaves laptop-mode behavior unchanged.

## Next

Unit `002-user-access-and-keys` (bolt 009) replaces the owner-chat-only `OwnerGuard` with
real `owner`/`invite` access modes and a `users` table (schema v7), and adds `/setkey`.
