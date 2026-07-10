---
unit: 003-savings-detection-notifications
bolt: 004-savings-detection-notifications
stage: design
status: complete
updated: 2026-07-05T00:00:00Z
---

# Technical Design — Savings Detection & Notifications

> Scope: Bolt `004` — US-007/008/009. Same hexagonal layering; **zero new third-party
> dependencies** — email via stdlib `smtplib`, Telegram via stdlib `urllib.request`
> against the Bot API (flagged **[ADR]**).

## Package Layout Changes

```text
src/booksaver/
├── domain/
│   └── savings.py            # SavingsOpportunity, EquivalenceVerdict, RejectionReason,
│                             #   EquivalenceGate, SavingsDetector (pure)
├── application/
│   ├── ports.py              # + Notifier, SavingsRepository protocols
│   └── savings_pipeline.py   # SavingsPipeline: results -> detect -> persist -> notify
├── infrastructure/
│   ├── notifications/
│   │   ├── __init__.py
│   │   ├── smtp_notifier.py       # stdlib smtplib (STARTTLS)
│   │   └── telegram_notifier.py   # stdlib urllib -> api.telegram.org
│   └── persistence/
│       ├── schema.sql             # v3: savings_opportunities table
│       └── sqlite_store.py        # + SqliteSavingsRepository
└── cli/commands.py           # run job pipes check results into SavingsPipeline;
                              # `booksaver savings list` command
```

## Config Extension

`NotificationSettings` gains SMTP fields (all non-secret; secrets stay in env per ADR-002):

```toml
[notifications]
email = "you@example.com"          # recipient
smtp_host = "smtp.gmail.com"       # sender SMTP server
smtp_port = 587                    # STARTTLS port (default)
smtp_username = "you@example.com"  # SMTP login; also the From address
telegram_chat_id = "123456789"
# secrets: BOOKSAVER_SMTP_PASSWORD, BOOKSAVER_TELEGRAM_BOT_TOKEN (env)
```

A channel is **configured** when its non-secret settings AND its secret are present;
unconfigured channels are skipped with a log line (not an error).

## Domain Design (`domain/savings.py`)

```python
class RejectionReason(Enum):
    DATES_DIFFER / PROPERTY_DIFFERS / ROOM_DIFFERS / NOT_REFUNDABLE /
    REFUNDABILITY_UNKNOWN / CURRENCY_MISMATCH / PRICE_NOT_LOWER

@dataclass(frozen=True)
class EquivalenceVerdict:
    equivalent: bool
    rejection_reason: RejectionReason | None

@dataclass(frozen=True)
class SavingsOpportunity:
    opportunity_id: str; booking_id: str; check_id: str
    baseline_price: Money; live_price: Money
    amount_saved: Money; percent_saved: Decimal  # 2dp
    validated_at: datetime; notified_at: datetime | None
```

`evaluate_equivalence(booking, check_result)` — pure function implementing the gate
table from the domain model (absence passes for dates/property/room; refundability must
be positively True).

`detect_savings(booking, check_result)` — returns
`SavingsOpportunity | RejectionReason`: gate first, then currency match, then strict
`live < baseline`. Percent = `(saved / baseline * 100).quantize(0.01)`.

## SavingsPipeline (application)

```python
class SavingsPipeline:
    def process(self, results: list[CheckResult]) -> list[SavingsOpportunity]:
        # for each SUCCESS result with a known booking:
        #   detect_savings() -> opportunity | rejection (rejection: log, continue)
        #   savings_repo.add(opportunity)
        #   outcomes = dispatcher.dispatch(opportunity, booking)
        #   if any channel succeeded: savings_repo.mark_notified(...)
```

Wired into the scheduler job in `cli/commands.py` right after
`monitor.run_all_active()` — same tick, same store connection.

## Notification Design (US-009)

Message content (both channels, same facts):
- booking id + confirmation id + property name
- baseline vs live price, amount saved, percent saved
- rebook pointer: `booksaver rebook <opportunity-id>`

**SmtpEmailNotifier**: `smtplib.SMTP(host, port)` → `starttls()` → `login(username,
password)` → `send_message()` (an `email.message.EmailMessage`). Raises on any failure.

**TelegramNotifier**: `urllib.request.urlopen` POST to
`https://api.telegram.org/bot{token}/sendMessage` with `{chat_id, text}` JSON,
10 s timeout. Raises on non-200 / `ok: false`.

**NotificationDispatcher**: iterates configured notifiers; each `send()` wrapped in
try/except; collects `ChannelOutcome(channel, ok, error)`. One failure never blocks the
other channel (US-009 acceptance criteria).

## Data Persistence — v3 migration

```sql
CREATE TABLE IF NOT EXISTS savings_opportunities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  TEXT NOT NULL UNIQUE,
    booking_id      TEXT NOT NULL REFERENCES bookings(booking_id),
    check_id        TEXT NOT NULL,
    baseline_amount TEXT NOT NULL,   -- Decimal string
    live_amount     TEXT NOT NULL,
    currency        TEXT NOT NULL,
    amount_saved    TEXT NOT NULL,
    percent_saved   TEXT NOT NULL,
    validated_at    TEXT NOT NULL,
    notified_at     TEXT
);
```

`SCHEMA_VERSION = 3`; no destructive migration needed (pure addition, `CREATE IF NOT
EXISTS` covers both fresh and upgrading databases; version row appended).

## New CLI Surface

| Command | Purpose |
|---------|---------|
| `booksaver savings list` | Show detected opportunities (id, booking, saved, notified) |

## Error Handling

| Error | Behaviour |
|-------|-----------|
| Currency mismatch | Logged, no opportunity, no alert (never false-positive) |
| Gate rejection | Logged with reason; silent to the user (US-008) |
| SMTP failure | Logged `NotificationFailed(email)`; Telegram still attempted |
| Telegram failure | Logged `NotificationFailed(telegram)`; email unaffected |
| Both channels fail | Opportunity persisted with `notified_at = NULL`; retried on next detection? No — MVP: visible via `booksaver savings list` |
| No channels configured | Opportunity persisted; warning logged once |

## Open Decisions for Stage 3 (ADR Analysis)

1. **Stdlib-only notification transports** (smtplib + urllib vs `requests`/`python-telegram-bot`).
