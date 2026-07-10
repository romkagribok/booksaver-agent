# Unit Brief: Telegram Rebook Gate

**Unit ID:** `004-telegram-rebook-gate`
**Intent:** `003-telegram-interface`
**Status:** Planned
**Build order:** 4

## Purpose

Move the guided-rebook confirmation experience to Telegram without weakening it. The rebook state
machine (intent 001 unit 004) is unchanged; this unit adds a Telegram `ConfirmationGate` adapter
(inline-keyboard yes/no per mandatory confirmation, audit trail with chat + message IDs) and a
**device-handoff** step: because the browser runs on the VPS, the final booking click is delegated to
the user's own device via a deep link reproducing property, dates, and occupancy — the VPS never
executes cancel or purchase.

## Dependencies on other units

| Unit | What this unit needs |
|------|----------------------|
| `003-conversational-booking-ops` | User-scoped savings opportunities, chat routing |
| intent-001 `004-guided-rebook` | `ConfirmationGate` port, rebook state machine, audit trail (extended with channel metadata) |

## Loose coupling / interfaces (design-level)

| Consumes | From |
|----------|------|
| `ConfirmationPrompt` / `ConfirmationAnswer` port | rebook state machine |
| Savings opportunity (property URL, dates, occupancy) | savings repository |

| Emits | To |
|-------|-----|
| Inline-keyboard prompts + recorded answers (channel=telegram, chat_id, message_id, timestamp) | audit trail |
| Deep-link handoff message + user-confirmed outcome (`completed` / `abandoned`) | rebook log |

## Recommended implementation order (within unit)

1. US-032 — Telegram ConfirmationGate adapter + audit metadata
2. US-033 — deep-link construction + completion follow-up dialog

## Completion criteria (unit-level)

- Every state-machine confirmation maps to exactly one answered inline prompt; timeouts abort safely.
- No cancel/purchase action can be triggered from the VPS browser (existing ActionGuard remains).
- Deep link opens the correct property with the opportunity's dates/occupancy.
- Rebook outcome (user-confirmed) lands in the existing rebook log.

---

## Story Files

- `US-032`
- `US-033`
