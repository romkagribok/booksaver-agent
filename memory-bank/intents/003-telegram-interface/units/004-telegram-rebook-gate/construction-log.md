# Construction Log: Telegram Rebook Gate

**Intent:** `003-telegram-interface`
**Unit:** `004-telegram-rebook-gate`
**Status:** Complete

## Bolt 011 — 2026-07-11T19:55:00Z → 2026-07-11T20:15:00Z

Delivered US-032 (Telegram `ConfirmationGate` adapter + audit trail) and US-033
(device-handoff deep link + completed/abandoned outcome follow-up) — the guided-rebook
confirmation experience is now available from Telegram, with the existing state machine
(intent 001 unit 004) and its safety guarantees completely unchanged.

- **Stages**: model → design → implement → test, all complete (see
  `memory-bank/bolts/011-telegram-rebook-gate/`).
- **Result**: 603/603 tests passing (30 new), ruff clean, mypy clean. `SCHEMA_VERSION`
  unchanged (still 8).
- **New module**: `infrastructure/telegram/rebook_gate.py` — `PendingPromptRegistry`,
  `wait_with_shutdown` (blocking bridge), `TelegramConfirmationGate` (`ConfirmationGate`
  port adapter), `_SessionIdCapturingRepo` (observes the service-assigned session_id
  without modifying the service), `TelegramNavigator` (`Navigator` callback — deep link,
  never a browser), `build_deep_link_url`, `run_outcome_followup`, `answer_callback`,
  `register_rebook_command` (`/rebook` command + returned `callback_handler`).
- **Changed, additive only**: `infrastructure/telegram/router.py` (`IncomingCallback`
  dataclass), `infrastructure/telegram/bot_loop.py` (`callback_handler` param +
  `callback_query` dispatch branch), `infrastructure/telegram/gateway.py` (wires
  `register_rebook_command` + `callback_handler` into `BotLoop`),
  `infrastructure/telegram/commands_readonly.py` (`HELP_TEXT` `+= "/rebook ..."`),
  `domain/value_objects.py` (`TelegramBotSettings.rebook_confirm_timeout_seconds`,
  default 600, validated `>= 30`), `application/load_config.py` (parses the new key).
- **Not touched** (frozen regression surface, verified via empty `git diff`):
  `domain/rebook.py`, `application/rebook_service.py`,
  `infrastructure/cli_confirmation.py`, the `rebook`/`rebook-log` sections of
  `cli/commands.py`. Also not touched (coordination with the parallel bolt-012 worker):
  `monitor/session_manager.py`, `infrastructure/persistence/session_store.py`, any
  cookie-import CLI wiring, `memory-bank/operations/`, README/docs, Dockerfile/compose.

Completion criteria met: every state-machine confirmation maps to exactly one answered
inline prompt; a timeout or a daemon shutdown while parked both decline fail-safe and
promptly (~1s, not the full timeout); no cancel/purchase action can be triggered from the
VPS browser (`TelegramNavigator` only ever sends chat messages — it holds no browser
reference at all); the deep link opens the correct property with the opportunity's
dates/occupancy; the rebook outcome (user-confirmed) lands in the existing rebook log,
queryable via `booksaver rebook-log <session-id>`.
