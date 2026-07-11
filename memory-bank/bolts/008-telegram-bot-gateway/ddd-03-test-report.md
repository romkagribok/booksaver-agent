---
unit: 001-telegram-bot-gateway
bolt: 008-telegram-bot-gateway
stage: test
status: complete
updated: 2026-07-11T18:20:00Z
---

# Test Report — Telegram Bot Gateway

## Summary

| Metric | Value |
|--------|-------|
| Total tests | **434 passed, 0 failed** |
| New in this bolt | 74 |
| Pre-existing (regression surface) | 360 — all green |
| Lint (`ruff check src/ tests/`) | clean |
| Types (`mypy src/`) | clean (60 files) |
| Network calls in tests | none — every Telegram client test injects a fake transport |

## New Test Coverage by Story

### US-023 — Update loop + offset durability + watchdog (27 tests)
- `tests/unit/telegram/test_client.py` (9): `TelegramBotClient` against a fake transport —
  `get_updates` request shape (offset omitted when `None`, timeout passed through),
  `send_message`/`edit_message_text`/`answer_callback_query`/`delete_message` hit the
  right method with the right body, `reply_markup` included when given, `ok: false`
  responses raise `TelegramApiError`.
- `tests/unit/telegram/test_offset_store.py` (6): round-trip save/load, overwrite,
  corrupt-file treated as "no offset," **persists across a new store instance**
  (simulating a restart — the story's core durability AC), 0600 file permissions.
- `tests/unit/telegram/test_bot_loop.py` (8): known-command dispatch, unknown-command
  reply, non-owner refusal (router never invoked), **offset advances past the last
  processed `update_id` and is persisted**, **a fresh `BotLoop` resumes `get_updates`
  from the persisted offset** (restart simulation), dialog-handler hand-off for
  non-command text, a `TelegramApiError` from `get_updates` does not crash the loop, a
  handler exception on one update does not stop the batch (the next update still
  dispatches).
- `tests/unit/daemon/test_lifecycle.py` (+5 to the existing suite): bot runner started
  alongside the scheduler and receives the *same* `stop_event` object as
  `scheduler.stop_event`; no bot thread is created when `bot_runner=None`; a crashing bot
  runner exits the process with code 1; a crashing `scheduler.run()` exits the process
  with code 1; a cleanly-completing bot runner does not raise. All pre-existing lifecycle
  tests (PID file lifecycle, already-running guard, stale-PID cleanup, `stop()`) pass
  unchanged against the new threaded `start()`.

### US-024 — Router + dialog framework + `/cancelflow` (20 tests)
- `tests/unit/telegram/test_router.py` (4): dispatch invokes the registered handler,
  unknown command returns `False` (not an exception), re-registering a command overwrites
  the handler, `known_commands()` is sorted.
- `tests/unit/telegram/test_dialogs.py` (10): starting a dialog returns the first prompt
  and marks the chat active; a valid answer advances to the next prompt; **an invalid
  answer re-prompts with the expected format and does not advance the step**; completing
  all steps calls `on_complete` with the accumulated answers and clears the active dialog;
  **`/cancelflow`-equivalent `cancel()` works from any step** and reports whether a dialog
  existed; dialogs are independent per chat; starting a new dialog replaces an active one;
  an empty-steps `DialogDefinition` is rejected at construction.
- `tests/unit/telegram/test_gateway.py::test_cancelflow_reports_no_active_dialog` and the
  end-to-end test cover `/cancelflow` wired through the real router + `BotLoop`.
- `tests/unit/telegram/test_access.py` (6): `RateLimiter` allows the first event per key,
  blocks a second within the window, allows again once the window elapses (fake clock),
  tracks keys independently; `OwnerGuard` recognizes the owner chat and refuses a stranger
  **exactly once** before the rate limiter silences further refusals.

### US-036 — Read-only inspection commands (16 tests)
- `tests/unit/telegram/test_commands_readonly.py` (10): `/start` welcome, `/help` lists
  every command, `/status` with no database reports "no bookings" + "pending first tick,"
  `/status` with a registered booking + a recorded check reports booking count and the
  check outcome, `/bookings` lists active bookings (and reports none-registered cleanly),
  `/savings` reports none-detected cleanly, `/checks` without an argument prompts usage,
  `/checks <id>` reports failure-code history and reports "no checks recorded" for an
  unknown booking id.
- `tests/unit/test_telegram_bot_config.py` (11): `[telegram_bot]` defaults when the
  section is absent, `enabled=true` with `owner_chat_id` parses, `enabled=true` without
  `owner_chat_id` is rejected with a `ConfigValidationError` naming the field,
  `poll_timeout_seconds` clamps both below 25 and above 50 and is kept as-is inside the
  range, a non-numeric `owner_chat_id` is rejected, `enabled=false` ignores a missing
  `owner_chat_id`; direct `TelegramBotSettings` construction enforces the same
  `owner_chat_id`-required and 25-50 bounds as a backstop for callers that bypass
  `load_config`.
- `tests/unit/telegram/test_gateway.py` (5): `build_bot_runner` returns `None` when
  disabled, returns `None` when enabled but the token env var is missing, returns a
  runnable when a client is injected, and an **end-to-end scripted-transport test**
  drives one owner `/status` call and one stranger call through the real
  `BotLoop`+`CommandRouter`+`OwnerGuard` wiring in a single pass, asserting the owner gets
  a status reply containing booking/uptime data and the stranger gets exactly one "this
  bot is private" refusal.

## Manual verification (not automated)

- `booksaver init` / `config validate` / `config show` exercised against a real config
  file: the new `telegram_bot.*` lines print correctly, defaults are `False`/`(not
  set)`/`30`.
- `booksaver run` started against a config with `telegram_bot.enabled = true` and no
  `BOOKSAVER_TELEGRAM_BOT_TOKEN` set: logs "Telegram bot gateway disabled" and the daemon
  runs and stops cleanly on `SIGTERM` (exit code 0) — confirms the disabled path never
  starts a second thread and never blocks shutdown.

## Deviations from the brief

- None functionally. One addition beyond the literal brief: `build_bot_runner()` accepts
  an optional `client: TelegramBotClient | None` parameter so tests can inject a
  fake-transport client through the *real* wiring path (not just the individual units) —
  production callers (`cli/commands.py`) never pass it, so the default behavior (build a
  client from the env-var token) is unchanged.
- `Scheduler` gained `stop_event`/`started_at`/`last_tick_at`/`next_run_at` — additive
  properties needed for `/status` and for the bot thread to share the shutdown signal;
  no existing method signature changed.
- `daemon/lifecycle.start()` now runs the scheduler on a background thread and joins it,
  rather than calling `scheduler.run()` inline on the calling thread — required so it can
  run alongside an optional bot thread and so the watchdog can `sys.exit(1)` after both
  have joined. Externally observable behavior (blocking until stopped, PID file written
  before start / removed in `finally`, `SystemExit(2)` for an already-running daemon) is
  unchanged and covered by the full pre-existing `test_lifecycle.py` suite passing as-is.
