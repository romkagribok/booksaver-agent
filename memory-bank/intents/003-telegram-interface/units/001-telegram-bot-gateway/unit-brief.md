# Unit Brief: Telegram Bot Gateway

**Unit ID:** `001-telegram-bot-gateway`
**Intent:** `003-telegram-interface`
**Status:** Complete (bolt 008)
**Build order:** 1

## Purpose

Add a bidirectional Telegram gateway to the daemon: a long-polling update loop (stdlib urllib,
extends ADR-011) running as a thread beside the scheduler, a command router, and a per-chat
conversation state machine for multi-step dialogs. Ships with read-only commands (`/start`, `/help`,
`/status`, `/bookings`, `/savings`, `/checks`) restricted to the configured owner chat ID — the
multi-user story is Unit 2. Delivers immediate value: the owner can inspect the daemon from their
phone.

## Dependencies on other units

| Unit | What this unit needs |
|------|----------------------|
| intent-001 `001-core-local-data` | Daemon lifecycle (add bot thread), config loading (`[telegram_bot]` section), SQLite stores |
| intent-001 `003-savings-detection-notifications` | Existing `TelegramNotifier` transport conventions (urllib + certifi), savings repository |
| intent-002 `002-agentic-escalation` | Check history + trace repositories for `/checks` |

## Downstream consumers

- Unit 2 replaces the owner-chat-only guard with real access control.
- Units 3–4 register their dialogs/commands on this router.

## Loose coupling / interfaces (design-level)

| Consumes | From |
|----------|------|
| `LocalConfig` (+ new `[telegram_bot]` block: token env var, owner chat ID, poll timeout) | core-local-data |
| Read repositories (bookings, savings, checks) | existing stores |

| Emits | To |
|-------|-----|
| `IncomingCommand(user_id, chat_id, command, args)` | router → application services |
| `ConversationState` transitions (persisted offset + per-chat dialog state) | Unit 3 dialogs |

## Recommended implementation order (within unit)

1. US-023 — Update loop thread + offset persistence + graceful shutdown
2. US-024 — Router + conversation state machine + `/help`, `/cancelflow`
3. US-036 — `/status` and read-only inspection commands

## Completion criteria (unit-level)

- Daemon runs scheduler + bot loop in one process; killing the daemon stops both cleanly.
- Owner can run all read-only commands from Telegram while a check is in progress.
- Non-owner chats receive a polite refusal; no state or LLM call is triggered.
- Update offset persisted: restart neither drops nor replays commands.

---

## Story Files

- `US-023`
- `US-024`
- `US-036`
