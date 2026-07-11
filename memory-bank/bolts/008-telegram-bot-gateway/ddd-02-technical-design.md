---
unit: 001-telegram-bot-gateway
bolt: 008-telegram-bot-gateway
stage: design
status: complete
updated: 2026-07-11T17:48:00Z
---

# Technical Design — Telegram Bot Gateway

> Scope: US-023, US-024, US-036. Runtime deps unchanged (stdlib urllib + certifi, no bot
> framework, no asyncio — ADR-003/ADR-008/ADR-011 extended, not amended).

## Module Map

| Module | Role | New/Changed |
|--------|------|--------------|
| `domain/value_objects.py` | + `TelegramBotSettings` (`enabled`, `owner_chat_id`, `poll_timeout_seconds`) | changed |
| `domain/models.py` | `Config` + `telegram_bot_settings: TelegramBotSettings` | changed |
| `application/load_config.py` | `[telegram_bot]` section parsing: `enabled` bool, `owner_chat_id` int (required if enabled), `poll_timeout_seconds` clamped 25-50 | changed |
| `infrastructure/telegram/client.py` | `TelegramBotClient` — urllib+certifi (copies `telegram_notifier.py`'s SSL pattern); `get_updates`/`send_message`/`edit_message_text`/`answer_callback_query`/`delete_message`; injectable `transport` for tests | **new** |
| `infrastructure/telegram/offset_store.py` | `TelegramOffsetStore` — plain file in the data dir (`telegram_offset`), same pattern as `session_store.py` | **new** |
| `infrastructure/telegram/router.py` | `IncomingCommand`, `CommandRouter` (registry API: `register`/`dispatch`/`known_commands`) | **new** |
| `infrastructure/telegram/dialogs.py` | `DialogStep`, `DialogDefinition`, `DialogManager` — the conversation state machine framework (no concrete dialogs yet) | **new** |
| `infrastructure/telegram/access.py` | `RateLimiter` (generic sliding-window, per-key), `OwnerGuard` (`is_owner`, `should_send_refusal`) | **new** |
| `infrastructure/telegram/commands_readonly.py` | `register_readonly_commands()` — `/start`, `/help`, `/status`, `/bookings`, `/savings`, `/checks <id>`; reads via existing `Sqlite*Repository` classes only | **new** |
| `infrastructure/telegram/bot_loop.py` | `BotLoop.run(stop_event)` — long-poll -> access-guard -> route/dialog -> advance+persist offset; retries on transient API/network errors | **new** |
| `infrastructure/telegram/gateway.py` | `build_bot_runner(config, db_path, scheduler, client=None)` — wires everything above into a `Callable[[threading.Event], None]`, or `None` if disabled/misconfigured | **new** |
| `daemon/scheduler.py` | + `stop_event` property (shared shutdown signal), `started_at`, `last_tick_at`, `next_run_at` (for `/status`) | changed, additive |
| `daemon/lifecycle.py` | `start(config, scheduler, bot_runner=None)` — scheduler now runs in its own thread (joined, not inline) so it can run alongside an optional bot thread; fail-fast watchdog: either thread's unhandled exception requests a stop and marks a failure, `sys.exit(1)` after both threads join | changed |
| `cli/commands.py` | `cmd_run` builds `bot_runner` via `build_bot_runner()` when `telegram_bot.enabled`; `_SAMPLE_CONFIG` gains a `[telegram_bot]` template block; `cmd_config_show` prints the three settings | changed |

## Threading design (US-023)

`lifecycle.start()`:
1. Writes the PID file (unchanged).
2. Installs `SIGTERM`/`SIGINT` handlers calling `scheduler.request_stop()` (unchanged
   mechanism, ADR-006).
3. Starts a `scheduler` thread running `scheduler.run(config.check_interval)`.
4. If `bot_runner` is given, starts a second thread running `bot_runner(scheduler.stop_event)`
   — the bot loop watches the *same* `threading.Event` the scheduler already uses, so a
   signal or either thread's crash stops both.
5. Joins both threads, then removes the PID file (`finally`, matching the pre-existing
   contract exercised by `test_lifecycle.py`).
6. If either thread's target caught an unhandled exception (watchdog), `sys.exit(1)` after
   the `finally` block — the daemon process exits nonzero so systemd/Docker's restart
   policy fires; a job's own exception inside `scheduler.run()`'s per-job loop is *not* a
   crash (existing per-job `except Exception` behavior is unchanged) — only `scheduler.run`
   itself raising, or the bot loop raising out of `BotLoop.run`, trips the watchdog.

This is additive: `bot_runner=None` (the default, and what `cmd_run` passes when
`[telegram_bot]` is absent or disabled) reproduces the exact prior behavior — one thread,
same PID-file lifecycle, same externally observable blocking semantics — confirmed by the
full pre-existing `test_lifecycle.py` suite passing unchanged.

## Update loop design (US-023)

`BotLoop.run(stop_event)`:
```
offset = offset_store.load()
while not stop_event.is_set():
    updates = client.get_updates(offset, timeout=poll_timeout)   # 25-50s long poll
    for update in updates:
        offset = update["update_id"] + 1
        dispatch(update)             # never lets one bad update crash the loop
    if updates:
        offset_store.save(offset)    # persisted only after the whole batch is handled
```
Transient `TelegramApiError`/`OSError` from `get_updates` are logged and retried after a
short wait rather than propagating — a network blip must not trip the fail-fast watchdog
(that is reserved for genuinely unhandled/programming errors).

`_dispatch(update)`:
- Ignores non-message updates (callback queries land in a later bolt).
- Resolves `chat_id`/`user_id` from `message.chat.id`/`message.from.id`.
- `access_guard(chat_id)` false -> `on_refused(chat_id)` (rate-limited single refusal),
  return — no router/dialog is ever reached.
- `/`-prefixed text -> `router.dispatch()`; unknown command -> one "unknown command" reply.
- Otherwise, if a `dialog_handler` is registered and the chat has an active dialog, the
  text is fed to `DialogManager.handle_message()`.

## Gateway wiring (`build_bot_runner`)

Builds one `TelegramBotClient`, `CommandRouter`, `DialogManager`, `OwnerGuard`, and
`TelegramOffsetStore` per daemon run; registers the six read-only commands plus
`/cancelflow` (which calls `DialogManager.cancel()`); returns `BotLoop.run` bound to that
wiring. Returns `None` (logging why) when `telegram_bot.enabled` is false or
`BOOKSAVER_TELEGRAM_BOT_TOKEN` is unset — `cmd_run` treats both identically (no thread
started). A `client` parameter can be injected (used by tests to supply a fake-transport
client) without changing the production path, which always builds its own client from the
env-var token (ADR-002 — the token itself never enters config.toml).

## `/status` data (US-036)

Reads `scheduler.started_at` (uptime), `scheduler.next_run_at` (`last_tick_at + interval`,
`None` before the first tick — reported as "pending first tick"), and, per active booking,
the most recent `CheckResult` via `SqliteCheckHistoryRepository.get_recent(id, limit=1)`.
No new persistence — purely a read projection over state the scheduler and existing
repositories already hold.
