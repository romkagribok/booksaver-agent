---
id: 011-telegram-rebook-gate
unit: 004-telegram-rebook-gate
intent: 003-telegram-interface
type: ddd-construction-bolt
status: complete
stories:
  - 001-confirm-rebook-in-telegram
  - 002-device-handoff-final-click
created: 2026-07-11T19:55:00Z
started: 2026-07-11T19:55:00Z
completed: 2026-07-11T20:15:00Z
current_stage: null
stages_completed:
  - name: model
    completed: 2026-07-11T20:00:00Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-11T20:05:00Z
    artifact: ddd-02-technical-design.md
  - name: implement
    completed: 2026-07-11T20:10:00Z
    artifact: >-
      infrastructure/telegram/rebook_gate.py (new) +
      infrastructure/telegram/{bot_loop,router,gateway,commands_readonly}.py +
      domain/value_objects.py (TelegramBotSettings.rebook_confirm_timeout_seconds) +
      application/load_config.py
  - name: test
    completed: 2026-07-11T20:15:00Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 008-telegram-bot-gateway
  - 010-conversational-booking-ops
requires_units:
  - 001-telegram-bot-gateway
  - 003-conversational-booking-ops
blocks: false
complexity:
  avg_complexity: 4
  avg_uncertainty: 4
  max_dependencies: 3
  testing_scope: 4
---

# Bolt: 011-telegram-rebook-gate

## Overview

Fourth bolt of intent 003. Moves the guided-rebook confirmation experience from the
terminal to Telegram without touching the rebook state machine or its safety
guarantees. `/rebook <opportunity-id>` starts the existing, unmodified
`RebookSessionService.run()` in a dedicated worker thread, wired with a new
`TelegramConfirmationGate` (`ConfirmationGate` port, inline-keyboard yes/no per mandatory
confirmation) and a new `TelegramNavigator` (`Navigator` callback) that never opens a
browser — it hands the user a Booking.com deep link reproducing the opportunity's
property, dates, and occupancy, to open and finish on their own device. A short
completed/abandoned follow-up dialog after the session records the user-reported outcome
into the existing rebook audit trail.

## Objective

A user acting on a `/savings` alert can run the entire mandatory-confirmation rebook flow
from their phone: each state-machine confirmation is one inline-keyboard tap, answers are
audited with channel/chat/message/timestamp, a timeout or daemon shutdown while parked
declines fail-safe (mirroring the CLI's EOF-declines behaviour), and the final cancel/book
clicks always happen on the user's own device — the VPS browser never performs them.

## Stories Included

- **US-032**: Confirm rebook steps in Telegram (Must)
- **US-033**: Device handoff for the final booking click (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: Complete → ddd-01-domain-model.md
- [x] **2. Technical Design**: Complete → ddd-02-technical-design.md
- [x] **3. Implement**: Complete → `infrastructure/telegram/rebook_gate.py` + minimal,
      additive extensions to `bot_loop.py`/`router.py`/`gateway.py`
- [x] **4. Test**: Complete → ddd-03-test-report.md (603/603; 33 new)

## Dependencies

### Requires
- Unit `001-telegram-bot-gateway` (bolt 008): `TelegramBotClient` (already supports
  `reply_markup`/`answer_callback_query`/`edit_message_text`), `CommandRouter`,
  `BotLoop`.
- Unit `003-conversational-booking-ops` (bolt 010): per-user-scoped savings
  opportunities (`SavingsRepository.list_all_for_user`), `UserRepository
  .get_owner_of_booking` (bolt 009), chat-reply rate limiting (reused unchanged).
- Intent 001 unit `004-guided-rebook` (bolt 005): `RebookSessionService`,
  `RebookSession` state machine, `ConfirmationGate`/`Navigator` ports, `rebook_events`
  audit trail. **Frozen** — no transitions, signatures, or event types changed.

### Enables
- Unit `005-vps-deployment` (bolt 012, parallel): no direct dependency; this bolt's
  worker-thread-per-session pattern (own `SqliteStore` connection, `daemon=True` thread)
  is the template a future async-check feature could reuse.

## Success Criteria

- [x] `/rebook <opportunity-id>` starts the unmodified `RebookSessionService` with a
      `TelegramConfirmationGate` in place of `TerminalConfirmationGate` — the CLI's
      `rebook`/`rebook-log` commands are untouched and still pass their existing tests.
- [x] Every mandatory confirmation is exactly one inline-keyboard prompt; only a tap from
      the prompt's own chat+user resolves it — other chats/users are silently ignored.
- [x] Every answered prompt logs an additive `rebook_events` row (`detail` free text)
      with `channel=telegram`, `chat_id`, `message_id`, ISO-8601 timestamp — no schema
      change (SCHEMA_VERSION stays 8).
- [x] No answer within `[telegram_bot].rebook_confirm_timeout_seconds` (default 600)
      declines fail-safe; the prompt message is edited so it can't be tapped twice.
- [x] A daemon shutdown (`stop_event`) while parked on a prompt declines within ~1s, not
      the full timeout — the worker thread exits promptly (bounded by polling, thread is
      `daemon=True`).
- [x] Exactly one active rebook session per user; a second `/rebook` while one is running
      gets a polite refusal, no second worker thread/session is started.
- [x] `/rebook <id>` on an opportunity the sender does not own is refused with the same
      message as an unknown id (no existence oracle).
- [x] The device-handoff deep link (US-033) reproduces property name, check-in/check-out,
      and occupancy (`group_adults`/`group_children`/`no_rooms`) using the same param
      names `monitor/search_journey.py` uses to reach the verified property page.
- [x] The VPS browser never navigates for cancel/book — `TelegramNavigator` only ever
      sends chat messages (ActionGuard, `InteractiveBrowser.act`, untouched).
- [x] Completed/abandoned outcome per handoff sent lands in the existing rebook log,
      queryable via `booksaver rebook-log <session-id>`; an unanswered outcome question
      records a distinct `status=unreported` event rather than nothing.

## Notes

- **Frozen regression surface honoured.** `domain/rebook.py` and
  `application/rebook_service.py` are byte-for-byte unchanged from the merge base — `git
  diff phase-3-telegram-interface -- src/booksaver/domain/rebook.py
  src/booksaver/application/rebook_service.py` is empty. Every Telegram-specific
  behaviour lives in the new adapter module; see ddd-02 for how the gate learns the
  session's `session_id` (which `ConfirmationGate.ask()` is never given) without
  modifying the service: a `_SessionIdCapturingRepo` wraps the injected
  `RebookSessionRepository` purely to observe `add()`.
- **No schema bump.** `rebook_events.detail` is unconstrained `TEXT`; Telegram audit
  metadata (`telegram_answer ...`, `telegram_handoff ...`, `telegram_outcome ...`) is
  additional rows appended by the gate/navigator alongside the service's own
  `CONFIRMATION_REQUESTED`/`CONFIRMED`/`DECLINED`/`ACTION_EXECUTED` rows, reusing the
  existing `EventType` values (no new enum members touch the frozen `domain/rebook.py`).
  `SCHEMA_VERSION` stays 8.
- **Callback routing wired minimally.** `router.py` gained one additive dataclass
  (`IncomingCallback`); `bot_loop.py` gained one additive constructor param
  (`callback_handler`) and a `callback_query` branch in `_dispatch` — `CommandRouter`
  itself is untouched, since only one feature consumes callback queries today.
  `client.py` needed no changes: `reply_markup`/`answer_callback_query`/
  `edit_message_text` already existed from bolt 008.
- **Deep link is our own, not the service's.** `RebookSessionService`'s internal
  `_rebook_url`/`_cancel_url` helpers build the URLs passed to `Navigator` — but
  `_rebook_url` has no occupancy params and is out of scope to change (frozen file). Per
  US-033's occupancy requirement, `TelegramNavigator` relays the service's URL as-is for
  the *first* (cancellation) call and substitutes its own occupancy-aware
  `build_deep_link_url(booking)` for the *second* (new-offer) call — order is
  structurally guaranteed by the state machine (cancel gate always precedes book gate).
- **One session per user, in-memory.** `_ActiveSessionGuard` is a process-lifetime
  `set[int]` guarded by a lock; a daemon restart clears it (acceptable — a stale
  in-flight session on restart is already interrupted by the same shutdown-decline path).
- **Coordination:** did not touch `monitor/session_manager.py`,
  `infrastructure/persistence/session_store.py`, any cookie-import CLI wiring,
  `memory-bank/operations/`, README/docs, or Dockerfile/compose (bolt 012's slice). Only
  additive edits to shared files (`gateway.py`, `bot_loop.py`, `router.py`,
  `load_config.py`, `value_objects.py`, `commands_readonly.py` HELP_TEXT,
  `story-index.md`).
