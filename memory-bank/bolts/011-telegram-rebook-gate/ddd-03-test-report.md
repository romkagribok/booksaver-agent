---
unit: 004-telegram-rebook-gate
bolt: 011-telegram-rebook-gate
stage: test
status: complete
updated: 2026-07-11T20:15:00Z
---

# Test Report — Telegram Rebook Gate

## Summary

| Metric | Value |
|--------|-------|
| Total tests | **603 passed, 0 failed** |
| New in this bolt | 30 |
| Pre-existing (regression surface, post Wave-2 merge) | 573 — all green, unchanged |
| Lint (`ruff check src/ tests/`) | clean |
| Types (`mypy src/`) | clean (71 files) |
| Network calls in tests | none — every test uses a `FakeClient` (thread-safe, in-process) implementing only `send_message`/`edit_message_text`/`answer_callback_query` |
| Flakiness check | `tests/unit/telegram/test_rebook_gate.py` run 4x consecutively (1x during dev, 3x post-fix), all green, sub-2s each — no timing-dependent failures observed |

## New Test Coverage by Story

### US-032 — Telegram `ConfirmationGate` + audit (`tests/unit/telegram/test_rebook_gate.py`, `tests/unit/telegram/test_bot_loop.py`, `tests/unit/test_telegram_bot_config.py`)

- **`PendingPromptRegistry`** (4 tests): resolve matches only the exact
  `(nonce, chat_id, user_id)`; a wrong chat, wrong user, or unknown nonce is a no-op that
  leaves the original prompt still pending and unresolved.
- **`wait_with_shutdown`** (3 tests): returns `True` immediately when the event is already
  set; returns `False` after a real timeout; returns `False` almost immediately (well
  under the requested timeout) when `stop_event` is set — the daemon-shutdown-while-parked
  requirement, tested directly against a 600s timeout to prove it doesn't wait it out.
- **`answer_callback`** (3 tests): a well-formed `rebook:<nonce>:yes|no` payload resolves
  the matching prompt and acks the callback query; malformed `data` is ignored (no crash,
  no ack side-channel abuse); a callback from the wrong chat is ignored for resolution
  purposes but the query is still acked (Telegram client spinner must stop regardless).
- **`TelegramConfirmationGate`** (5 tests): explicit "Yes" tap approves and the message is
  edited to show the choice (can't be tapped twice); explicit "No" declines, message
  edited; no answer within the timeout declines fail-safe with an "Expired" edit; a set
  `stop_event` declines within ~1s even against a 600s timeout, edit says "shutting down";
  an answer tapped from a different chat is ignored and the real prompt still times out
  and declines (proves the wrong-chat tap cannot forge an approval).
- **`answer_callback`/`bot_loop` routing** (2 tests, `test_bot_loop.py`): a `callback_query`
  update with a registered `callback_handler` is parsed into an `IncomingCallback` with
  the correct `chat_id`/`user_id`/`message_id`/`data`; with no `callback_handler`
  configured, a `callback_query` update is silently ignored (loop doesn't crash, no reply
  sent) — covers a daemon running with the bot gateway but this feature not wired in yet.
- **Config** (5 tests, `test_telegram_bot_config.py`): `rebook_confirm_timeout_seconds`
  defaults to 600 both via `load_config` and direct `TelegramBotSettings()` construction;
  a custom value round-trips through `load_config`; values below 30 are rejected at both
  layers with a message naming the field.
- **`register_rebook_command`** ownership + concurrency (3 tests): `/rebook <id>` on an
  opportunity owned by a different local user is refused with the identical "No savings
  opportunity found" message a genuinely unknown id gets (no existence oracle); a second
  `/rebook` while the first is still parked on its cancel-confirmation gets a polite
  "already have a rebook session in progress" refusal and does **not** start a second
  worker thread (verified by then answering the first session and observing exactly one
  "ended: declined" reply); `/rebook` with no args lists only the sender's own
  opportunities by full `opportunity_id` (needed verbatim for the next `/rebook <id>`
  call).

### US-033 — Device handoff + outcome follow-up (`tests/unit/telegram/test_rebook_gate.py`)

- **`build_deep_link_url`** (1 test): the URL contains `ss=<property name, url-encoded>`,
  `checkin=`/`checkout=` matching the booking's stay dates, and
  `group_adults`/`group_children`/`no_rooms` matching the booking's `Occupancy` exactly —
  same param names `search_journey.py` uses.
- **`TelegramNavigator`** (1 test): the first `navigate()` call relays the service-provided
  cancellation URL as-is; the second call ignores the service-provided (occupancy-less)
  `_rebook_url` and sends `build_deep_link_url(booking)` instead, verified by asserting
  `group_adults=3` (a non-default occupancy) appears in the second sent message; both
  calls append a `telegram_handoff` audit event with the right `kind` (`cancel`/`book`).
- **`run_outcome_followup`** (2 tests): asks one question per handoff actually sent, in
  order; a "Completed"/"Abandoned" tap records `status=completed`/`status=abandoned`; no
  answer within the timeout records `status=unreported` — and does **not** ask a second
  question for a handoff that was never sent (only `cancel_handoff_sent` was set, so only
  one question fires).
- **End-to-end happy path** (1 test, `test_rebook_happy_path_end_to_end`): drives the full
  flow through `register_rebook_command`'s real `/rebook` handler and returned
  `callback_handler` — cancel confirmation (tap Yes) -> cancel handoff message ->
  book confirmation (tap Yes) -> book handoff deep link (asserts `group_adults=2`,
  matching the fixture booking's occupancy) -> session-ended reply -> two outcome
  questions (both tapped "Completed"). Verifies, by reading the *real* `SqliteStore`
  after the flow: exactly one `rebook_sessions` row for the opportunity, and its
  `rebook_events` contain `telegram_answer`, `telegram_handoff`, and both
  `telegram_outcome kind=... status=completed` entries — proving the audit trail lands in
  the same persisted mechanism `booksaver rebook-log` already reads.

## Regression Verification

- **CLI rebook path unchanged**: `domain/rebook.py`, `application/rebook_service.py`,
  `infrastructure/cli_confirmation.py`, and the `rebook`/`rebook-log` sections of
  `cli/commands.py` were not edited — confirmed via `git diff phase-3-telegram-interface
  --stat` showing none of those four files touched. Their existing suites
  (`tests/unit/rebook/test_rebook_service.py`, `tests/unit/rebook/test_state_machine.py`,
  `tests/integration/test_rebook_repos.py`) all still pass unmodified, exercising the
  identical `RebookSessionService`/`RebookSession`/`TerminalConfirmationGate` code path
  this bolt's Telegram adapter now also drives.
- **`SCHEMA_VERSION` unchanged** (still 8): `tests/integration/test_user_scoping.py` and
  every persistence test that asserts on schema/migration behavior pass unmodified — no
  new table, no new column, no new `_MIGRATIONS` entry was needed for this bolt.
- **Existing Telegram gateway/bot-loop/dialog suites** (`test_gateway.py`,
  `test_bot_loop.py`, `test_dialogs.py`, `test_register_dialog.py`, `test_access*.py`,
  `test_admin_commands.py`, `test_key_dialogs.py`, `test_commands_readonly.py`) all pass
  unmodified except the two additive `test_bot_loop.py` cases above — confirms the new
  `callback_handler` parameter and `HELP_TEXT` line didn't perturb existing command
  dispatch, dialog routing, or access-control behavior.

## Commands Run

```bash
python3 -m ruff check src/ tests/          # All checks passed!
python3 -m mypy src/                       # Success: no issues found in 71 source files
PYTHONPATH=src python3 -m pytest -q        # 603 passed in ~5s
```
