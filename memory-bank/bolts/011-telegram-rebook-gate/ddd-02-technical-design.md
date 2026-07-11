---
unit: 004-telegram-rebook-gate
bolt: 011-telegram-rebook-gate
stage: design
status: complete
updated: 2026-07-11T20:05:00Z
---

# Technical Design — Telegram Rebook Gate

> Scope: US-032, US-033. No new runtime deps (ADR-003 stdlib-first held; `threading`,
> `uuid`, `urllib.parse` are stdlib). **No `SCHEMA_VERSION` bump — still 8.**
> `domain/rebook.py` and `application/rebook_service.py` are unchanged (verified by an
> empty `git diff` against the merge base for both files).

## Module Map

| Module | Role | New/Changed |
|--------|------|--------------|
| `infrastructure/telegram/rebook_gate.py` | Everything Telegram-rebook-specific: `PendingPromptRegistry`, `wait_with_shutdown`, `TelegramConfirmationGate`, `_SessionIdCapturingRepo`, `TelegramNavigator`, `build_deep_link_url`, `run_outcome_followup`, `answer_callback`, `register_rebook_command` | **new** |
| `infrastructure/telegram/router.py` | + `IncomingCallback` dataclass (mirrors `IncomingCommand` for `callback_query` updates) | changed, additive |
| `infrastructure/telegram/bot_loop.py` | `BotLoop.__init__` gains optional `callback_handler: Callable[[IncomingCallback], None] \| None`; `_dispatch` branches on `update["callback_query"]` before falling through to the existing message path; new `_dispatch_callback` | changed, additive |
| `infrastructure/telegram/gateway.py` | Wires `register_rebook_command(...)`, passes its returned handler into `BotLoop(callback_handler=...)` | changed, additive block |
| `infrastructure/telegram/commands_readonly.py` | `HELP_TEXT` gains one `/rebook` line | changed, cosmetic |
| `domain/value_objects.py` | `TelegramBotSettings` + `rebook_confirm_timeout_seconds: int = 600`, validated `>= 30` | changed, additive field |
| `application/load_config.py` | `[telegram_bot]` parsing block reads the new key (defaults from `TelegramBotSettings()`) | changed, additive |
| `infrastructure/cli_confirmation.py`, `application/rebook_service.py`, `domain/rebook.py`, `cli/commands.py` (rebook section) | — | **untouched** |

## The blocking bridge, precisely

```
bot loop thread                          worker thread ("rebook-<opp[:8]>", daemon=True)
────────────────                          ───────────────────────────────────────────────
router.dispatch("/rebook <id>")
  -> ownership + concurrency checks
  -> spawns worker thread, returns          RebookSessionService.run(opportunity_id)
                                               -> gate.ask(prompt)              [Gate 1: cancel]
                                                    nonce = uuid4().hex
                                                    client.send_message(inline keyboard)
                                                    registry.register(nonce, pending)
                                                    wait_with_shutdown(pending.event,
                                                                        stop_event, timeout)
callback_query arrives (poll loop)                      ⋮ (parked)
  -> BotLoop._dispatch_callback
  -> callback_handler(IncomingCallback)
  -> answer_callback(registry, client, cb)
       registry.resolve(nonce, chat_id,
                         user_id, approved)
         -> pending.approved = approved
         -> pending.event.set()  ─────────────────────────► event.wait() returns True
                                               edit_message_text(outcome)
                                               append RebookEvent(telegram_answer ...)
                                               return ConfirmationAnswer(approved, now)
                                             -> session.approve()/.decline() [state machine]
                                             -> navigator(url, description)   [Navigator]
                                               (TelegramNavigator: send_message + audit)
                                             -> gate.ask(prompt)              [Gate 2: book]
                                                    (same shape as Gate 1)
                                             -> session terminal
                                           run_outcome_followup(...)           [US-033]
                                           reply(chat_id, "ended: <state>")
```

`wait_with_shutdown` polls both `pending.event` and `stop_event` at
`_POLL_INTERVAL_SECONDS` (1.0s) granularity instead of a single `event.wait(timeout)` —
the only way a single `threading.Event.wait` could also observe a *second*,
independently-set event (`stop_event`) without a callback/condition-variable rewrite.
This bounds shutdown latency to ~1s regardless of `rebook_confirm_timeout_seconds`
(default 600s), satisfying "daemon shutdown while parked declines promptly."

## Why a session-id-capturing repository, not a service change

`ConfirmationGate.ask(prompt: ConfirmationPrompt) -> ConfirmationAnswer` — the port
signature (frozen) never passes the `RebookSession` or its `session_id` to the gate. The
audit requirement (US-032: "channel, chat_id, message_id, timestamp per answer") needs
the real `session_id` to append a correctly-scoped `rebook_events` row. Since
`RebookSessionService.run()` is not to be modified, `_SessionIdCapturingRepo` wraps the
`RebookSessionRepository` the service is given: its `add()` observes the session_id
`RebookSession.start()` generated (the service always calls `session_repo.add(session)`
before the first `gate.ask()`), stashes it into a `dict` box shared by reference with the
gate and navigator, and delegates unchanged to the real repository for every method. This
is strictly an observer — no behavior of the repository changes.

## Why the navigator rebuilds the second URL

`RebookSessionService._rebook_url(booking)` (private, in the frozen `rebook_service.py`)
builds `https://www.booking.com/searchresults.html?ss=...&checkin=...&checkout=...` — no
occupancy params. US-033 requires the deep link to carry occupancy
(`group_adults`/`group_children`/`no_rooms`), matching how `search_journey.py`'s
`_search_results_url` reaches the *verified* property page. Since the `Navigator`
signature is `(url: str, description: str) -> None` — it receives the service's chosen
URL, not a hook to build its own — `TelegramNavigator` uses order, not content matching:
the state machine's gates are structurally sequential (`await_cancel_confirmation()` ->
... -> `mark_cancel_executed()` -> `AWAITING_BOOK_CONFIRMATION` -> ... ->
`mark_book_executed()`), so the *first* `navigate()` call is always the cancellation step
and the *second* is always the book step. `TelegramNavigator` tracks this with one
boolean (`cancel_handoff_sent`) rather than string-matching the description, which is
more robust to the service's copy changing.

## Config: `[telegram_bot].rebook_confirm_timeout_seconds`

Added to the *existing* `TelegramBotSettings` dataclass (not a new `[rebook]` section) —
it is a Telegram-bot-loop concern (how long a chat prompt stays open), analogous to
`poll_timeout_seconds`. Default 600 (10 minutes); validated `>= 30` at both direct
construction and `load_config` (same two-layer validation pattern `poll_timeout_seconds`
and `access_mode` already use). `load_config`'s existing `telegram_bot` parsing `try`
block gained one more `int(...)` read with a default sourced from a fresh
`TelegramBotSettings()` instance — no duplicated literal `600`.

## Callback routing: why not through `CommandRouter`

`CommandRouter` maps a *command string* (`"/rebook"`) to a handler; a `callback_query`
carries no command, just an opaque `data` payload (`"rebook:<nonce>:<yes|no>"`) meaningful
only to whichever feature issued the nonce. Since exactly one feature (this bolt) consumes
callback queries today, routing it through one injected `BotLoop(callback_handler=...)`
function is simpler than adding a second registry to `CommandRouter` for a single
consumer; a second callback-query feature can prefix its own `data` and share the same
handler, or `CommandRouter` can grow a real sub-router at that point without touching
`bot_loop.py` again.

## Thread-safety / resource-ownership

- The worker thread opens its **own** `SqliteStore(db_path)` connection (`with
  SqliteStore(db_path) as store:` inside `_run_session`) — never the bot loop's — matching
  every other per-call pattern in this codebase (`commands_readonly.py`,
  `register_dialog.py`).
- `PendingPromptRegistry` and `_ActiveSessionGuard` are the only state shared between the
  bot loop thread and rebook worker threads; both are single-lock-protected, no nested
  locking, no risk of deadlock between them (registry lock and guard lock are never held
  simultaneously).
- Worker threads are `daemon=True` — a process exit (or watchdog-triggered
  `sys.exit`) never blocks on them; combined with the ~1s shutdown-decline latency, a
  parked session unwinds cleanly well within any reasonable shutdown grace period.
