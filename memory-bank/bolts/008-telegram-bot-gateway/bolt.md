---
id: 008-telegram-bot-gateway
unit: 001-telegram-bot-gateway
intent: 003-telegram-interface
type: ddd-construction-bolt
status: complete
stories:
  - 001-run-telegram-update-loop
  - 002-route-commands-and-dialogs
  - 003-inspect-daemon-from-chat
created: 2026-07-11T17:39:20Z
started: 2026-07-11T17:39:20Z
completed: 2026-07-11T18:20:00Z
current_stage: null
stages_completed:
  - name: model
    completed: 2026-07-11T17:45:00Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-11T17:48:00Z
    artifact: ddd-02-technical-design.md
  - name: adr
    completed: 2026-07-11T17:50:00Z
    artifact: adr-018-self-hosted-deployment.md
  - name: implement
    completed: 2026-07-11T18:10:00Z
    artifact: infrastructure/telegram/{client,offset_store,router,dialogs,access,commands_readonly,bot_loop,gateway}.py + daemon/{scheduler,lifecycle}.py + domain/value_objects.py (TelegramBotSettings) + application/load_config.py + cli/commands.py wiring
  - name: test
    completed: 2026-07-11T18:20:00Z
    artifact: ddd-03-test-report.md
requires_bolts: []
requires_units:
  - 001-core-local-data
  - 003-savings-detection-notifications
  - 002-agentic-escalation
enables_bolts:
  - 009-user-access-and-keys
blocks: false
complexity:
  avg_complexity: 4
  avg_uncertainty: 3
  max_dependencies: 3
  testing_scope: 4
---

# Bolt: 008-telegram-bot-gateway

## Overview

First bolt of intent 003. Adds a bidirectional Telegram gateway to the daemon: a
long-polling update loop (stdlib urllib + certifi, extends ADR-011) running as a thread
beside the scheduler, a command router with a registry API for later bolts, a per-chat
conversation state machine framework for multi-step dialogs, an owner-only access guard,
and read-only inspection commands (`/status`, `/bookings`, `/savings`, `/checks`). Ships
alongside a fail-fast watchdog so a crashed scheduler or bot thread exits the whole daemon
nonzero instead of leaving it half-alive.

## Objective

The owner can inspect the daemon (`/status`, `/bookings`, `/savings`, `/checks`) from
Telegram while scheduled checks run, with commands and offset durability surviving a
daemon restart, and every non-owner chat refused politely and rate-limited. No domain
logic lives in the bot layer — every handler reads through the same SQLite repositories
the CLI uses.

## Stories Included

- **US-023**: Run Telegram update loop inside the daemon (Must)
- **US-024**: Route commands and multi-step dialogs (Must)
- **US-036**: Inspect daemon health and history from chat (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: Complete → ddd-01-domain-model.md
- [x] **2. Technical Design**: Complete → ddd-02-technical-design.md
- [x] **3. ADR Analysis**: Complete → adr-018-self-hosted-deployment.md
- [x] **4. Implement**: Complete → telegram gateway package + daemon wiring + config
- [x] **5. Test**: Complete → ddd-03-test-report.md (434/434; 74 new)

## Dependencies

### Requires
- Unit `001-core-local-data` (daemon lifecycle, config loading, SQLite stores)
- Unit `003-savings-detection-notifications` (`TelegramNotifier` urllib+certifi pattern)
- Unit `002-agentic-escalation` (check history + trace repositories for `/checks`)

### Enables
- Bolt 009 (`002-user-access-and-keys`) replaces the owner-chat-only guard with real
  multi-user access modes and registers on the same router.
- Bolts 010-011 register their own commands/dialogs on this router without gateway changes.

## Success Criteria

- [x] Daemon runs scheduler + bot loop in one process; killing the daemon stops both
      cleanly (SIGTERM/SIGINT → `scheduler.request_stop()` → both threads join).
- [x] Owner can run all read-only commands from Telegram while a check is in progress
      (bot loop owns its own SQLite connection; never touches the browser).
- [x] Non-owner chats receive exactly one polite refusal per rate-limit window; no state
      change or LLM call is ever triggered for them.
- [x] Update offset persisted to `telegram_offset` in the data directory: a restart
      neither drops nor replays commands.
- [x] Fail-fast watchdog: either thread crashing exits the daemon process nonzero.
- [x] `[telegram_bot]` absent → daemon behaves exactly as before (laptop mode unaffected).

## Notes

- The conversation-state-machine framework (`DialogManager`/`DialogDefinition`) ships with
  no real dialogs in this bolt — registration/key-intake/rebook dialogs are unit 3/4 work.
  State is in-memory only; a restart mid-dialog resets to "no active dialog" rather than
  replaying or crashing (matches the story's "or is safely reset" acceptance criterion).
- `Scheduler` gained `stop_event`/`started_at`/`next_run_at` for `/status` and for the bot
  thread to share the same shutdown signal — additive, no behavior change to existing
  scheduler tests.
- `daemon/lifecycle.start()` now runs the scheduler in its own thread (previously it ran
  inline on the calling thread) so it can be joined alongside the optional bot thread; the
  externally observable behavior (blocks until stopped, PID file lifecycle) is unchanged,
  confirmed by the full existing `test_lifecycle.py` suite staying green.
- `_make_llm_extractor`/`_make_agent_brain`/`sqlite_store.py`/schema were intentionally left
  untouched per the coordination note in this bolt's brief — a parallel worker owns schema
  v7 (`users` table) and those two factory functions.
