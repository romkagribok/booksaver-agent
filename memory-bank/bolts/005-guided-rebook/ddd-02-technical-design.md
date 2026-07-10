---
unit: 004-guided-rebook
bolt: 005-guided-rebook
stage: design
status: complete
updated: 2026-07-05T00:00:00Z
---

# Technical Design — Guided Rebook

> Scope: Bolt `005` — US-010/011/012. Zero new dependencies; reuses BrowserSession
> (Unit 2) and SavingsOpportunity (Unit 3). One ADR candidate: guided-final-click
> MVP boundary **[ADR]**.

## Package Layout Changes

```text
src/booksaver/
├── domain/
│   └── rebook.py             # RebookSession state machine, RebookEvent,
│                             #   ConfirmationPrompt/Answer, SessionState enum
├── application/
│   ├── ports.py              # + ConfirmationGate, RebookSessionRepository,
│   │                         #   RebookEventRepository
│   └── rebook_service.py     # RebookSessionService — orchestrates the flow
├── infrastructure/
│   ├── cli_confirmation.py   # stdin ConfirmationGate ("yes" or decline)
│   └── persistence/
│       ├── schema.sql        # v4: rebook_sessions + rebook_events
│       └── sqlite_store.py   # + SqliteRebookSessionRepository, SqliteRebookEventRepository
└── cli/commands.py           # `booksaver rebook <opportunity-id>` + `rebook log <session-id>`
```

## Domain Design (`domain/rebook.py`)

```python
class SessionState(Enum):
    STARTED / AWAITING_CANCEL_CONFIRMATION / CANCEL_APPROVED /
    AWAITING_BOOK_CONFIRMATION / BOOK_APPROVED / COMPLETED / DECLINED / ERROR

class EventType(Enum):
    STARTED / CONFIRMATION_REQUESTED / CONFIRMED / DECLINED /
    ACTION_EXECUTED / COMPLETED / ERROR
```

`RebookSession` is a small class (not frozen — it is the one mutable aggregate) whose
state can only change through transition methods that validate the current state:

```python
def await_cancel_confirmation(self) -> None   # STARTED -> AWAITING_CANCEL_CONFIRMATION
def approve(self) -> None                      # AWAITING_X -> X_APPROVED
def decline(self) -> None                      # AWAITING_X -> DECLINED (terminal)
def mark_cancel_executed(self) -> None         # CANCEL_APPROVED -> AWAITING_BOOK_CONFIRMATION
def mark_book_executed(self) -> None           # BOOK_APPROVED -> COMPLETED (terminal)
def fail(self, detail) -> None                 # any non-terminal -> ERROR (terminal)
```

Illegal transitions raise `IllegalTransition(BookSaverError)`. `ConfirmationAnswer.from_input(text)`
approves ONLY on `"yes"`/`"y"` (case-insensitive, stripped); everything else declines.

## RebookSessionService (application)

```python
def run(self, opportunity_id: str) -> RebookSession:
    # 1. load opportunity + booking (unknown id -> error, exit 2)
    # 2. session = RebookSession.start(...); events.append(STARTED); sessions.add
    # 3. cancel gate:
    #      prompt = ConfirmationPrompt(action=CANCEL_EXISTING, old, new, refund summary)
    #      events.append(CONFIRMATION_REQUESTED)
    #      answer = gate.ask(prompt)
    #      declined -> session.decline(); events.append(DECLINED); return (nothing executed)
    #      approved -> session.approve(); events.append(CONFIRMED)
    # 4. execute cancel step (guided): browser opens the reservation's cancellation page;
    #      user completes the final click; events.append(ACTION_EXECUTED)
    # 5. book gate: same cycle, fresh confirmation (US-011: each destructive step anew)
    # 6. execute book step (guided): browser opens the property page for the same
    #      dates/room; user completes purchase; events.append(ACTION_EXECUTED)
    # 7. session COMPLETED; events.append(COMPLETED)
    # any exception -> session.fail(); events.append(ERROR); re-raise as exit-2 message
```

The browser is optional at runtime: with `--no-browser` (or Playwright unavailable) the
service prints the URL to visit instead of opening it. The state machine and audit trail
are identical either way — the gates are the product, not the navigation.

## v4 Migration

```sql
CREATE TABLE IF NOT EXISTS rebook_sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL UNIQUE,
    opportunity_id TEXT NOT NULL,
    booking_id     TEXT NOT NULL REFERENCES bookings(booking_id),
    state          TEXT NOT NULL,
    started_at     TEXT NOT NULL,
    ended_at       TEXT,
    end_reason     TEXT
);

CREATE TABLE IF NOT EXISTS rebook_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT NOT NULL UNIQUE,
    session_id  TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL
);
```

Purely additive → `_MIGRATIONS[4] = []`, `SCHEMA_VERSION = 4`.

## CLI Surface

| Command | Purpose |
|---------|---------|
| `booksaver rebook <opportunity-id>` | Start a guided rebook session (blocks at gates) |
| `booksaver rebook <opportunity-id> --no-browser` | Same flow, prints URLs instead of opening a browser |
| `booksaver rebook-log <session-id>` | Show the audit trail for a session |

## Error Handling

| Error | Behaviour |
|-------|-----------|
| Unknown opportunity id | Clear message + exit 2, no session created |
| Decline at any gate | Session `DECLINED`, event logged, exit 0 ("nothing was changed") |
| Browser failure mid-session | Session `ERROR`, event logged with detail, exit 2; no retry of destructive steps |
| Ctrl-C at a gate | Treated as decline (fail-safe) |

## Open Decisions for Stage 3 (ADR Analysis)

1. **Guided final click** — MVP navigates to the right page but leaves Booking.com's
   final cancel/purchase buttons to the human. **[ADR]**
