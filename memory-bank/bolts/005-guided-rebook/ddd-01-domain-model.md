---
unit: 004-guided-rebook
bolt: 005-guided-rebook
stage: model
status: complete
updated: 2026-07-05T00:00:00Z
---

# Domain Model — Guided Rebook

> Scope: Bolt `005-guided-rebook` — **US-010** (explicit intent), **US-011** (mandatory
> confirmation), **US-012** (local audit trail). The safety unit: its invariants are the
> product's core trust promise.

## Bounded Context

**Guided Rebook** owns the rebook session lifecycle. It consumes `SavingsOpportunity`
(Unit 3), `Booking` (Unit 1), and the `BrowserSession` port (Unit 2). It owns:

1. **The session state machine** — the only path to a destructive action, with
   confirmation gates hard-wired into the transitions.
2. **The audit trail** — every session event appended to local storage.

The daemon's scheduler NEVER creates a session; only the CLI (explicit human intent)
does. This is a structural guarantee, not a convention.

## The State Machine (core of US-010/011)

```
     [CLI: booksaver rebook <id>]
                │
                ▼
            STARTED ──────────────────────────┐
                │ prepare()                    │
                ▼                              │
        AWAITING_CANCEL_CONFIRMATION ──decline─┤
                │ confirm_cancel()             │
                ▼                              │
         CANCEL_APPROVED                       │
                │ execute_cancel()             │
                ▼                              │
        AWAITING_BOOK_CONFIRMATION ───decline──┤
                │ confirm_book()               │
                ▼                              │
          BOOK_APPROVED                        │
                │ execute_book()               │
                ▼                              ▼
            COMPLETED                    DECLINED (safe end)

        any step may also end in ERROR (logged, no further actions)
```

**Invariants:**
- `execute_cancel()` is only legal in `CANCEL_APPROVED`; `execute_book()` only in
  `BOOK_APPROVED`. Any other state raises — the type/state system forbids destruction
  without confirmation.
- Each approval is single-use: executing the approved action transitions AWAY from the
  approved state; a second destructive step needs a new confirmation cycle (US-011
  "each subsequent destructive step requires a new confirmation").
- `decline` from any awaiting state → `DECLINED`, session over, nothing executed.
- Confirmation input comes only from the local interface (stdin yes/no in MVP).

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| **RebookSession** (aggregate root) | `sessionId`, `opportunityId`, `bookingId`, `state` (enum above), `startedAt`, `endedAt` (nullable), `endReason` (nullable: `completed`/`declined`/`error`) | Created only via CLI intent; state transitions only through defined methods; terminal states are `COMPLETED`, `DECLINED`, `ERROR` |
| **RebookEvent** | `eventId`, `sessionId`, `eventType` (`started`, `confirmation_requested`, `confirmed`, `declined`, `action_executed`, `completed`, `error`), `detail` (text), `occurredAt` | Append-only; every transition writes exactly one event; never updated or deleted |

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| **ConfirmationPrompt** | `action` (`cancel_existing` / `book_new`), `oldPrice` (Money), `newPrice` (Money), `refundabilitySummary` (str) | Shows "what will happen" per US-011: old vs new price + refundability |
| **ConfirmationAnswer** | `approved` (bool), `answeredAt` | Only `yes` (exact, case-insensitive) approves; anything else declines — fail-safe default |

## Domain Events (audit trail, US-012)

Every `RebookEvent.eventType` above is the audit trail. Realized as rows in a local
`rebook_events` table (not just log lines — queryable per session).

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| **RebookSessionService** | `start(opportunity, booking) -> RebookSession`; `request_confirmation(session, prompt) -> None` (records event, waits); `apply_answer(session, answer) -> RebookSession` (transition per state machine); `execute_approved_action(session) -> RebookSession` | `RebookEventRepository`, `ConfirmationGate` port, `BrowserSession` port (prepare/navigate only in MVP) |

## Ports (new)

| Port | Operations | Adapters |
|------|------------|----------|
| **ConfirmationGate** | `ask(prompt: ConfirmationPrompt) -> ConfirmationAnswer` | Terminal stdin adapter (MVP); future Telegram bot |
| **RebookSessionRepository** | `add(session)`, `update(session)`, `get(sessionId)` | SQLite (v4) |
| **RebookEventRepository** | `append(event)`, `list_for_session(sessionId)` | SQLite (v4) |

## MVP Scope Boundary

The MVP `execute_cancel` / `execute_book` steps **navigate the browser to the right
page and hand control to the user** (guided), rather than clicking Booking.com's final
buttons programmatically. The state machine, confirmation gates, and audit trail are
fully real; the final click stays human. This satisfies every acceptance criterion
(automation "prepares the rebook path", stops at gates, only proceeds per approved
action) while avoiding automation of an irreversible money action against a layout we
cannot regression-test — the strongest reading of the product's safety constraint.

## Ubiquitous Language Additions

| Term | Meaning |
|------|---------|
| **Session** | One guided rebook attempt for one opportunity, from explicit start to terminal state |
| **Gate** | A blocking confirmation prompt; the only way past it is an explicit local "yes" |
| **Destructive action** | Cancel existing reservation or purchase new one — anything moving money or itinerary |
| **Fail-safe default** | Any answer other than an explicit yes is a decline |
| **Audit trail** | Append-only local record of every session event |
