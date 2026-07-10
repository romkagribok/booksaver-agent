---
unit: 003-savings-detection-notifications
bolt: 004-savings-detection-notifications
stage: model
status: complete
updated: 2026-07-05T00:00:00Z
---

# Domain Model — Savings Detection & Notifications

> Scope: Bolt `004-savings-detection-notifications` — **US-007** (baseline comparison),
> **US-008** (equivalence + refundability gate), **US-009** (email + Telegram alerts).

## Bounded Context

**Savings Detection & Notifications** is the pure-evaluation context. It consumes
`Booking` (Unit 1) and successful `CheckResult`s (Unit 2), applies the equivalence and
refundability gate, compares prices, and emits alerts. It owns:

1. **The savings verdict** — the single place that decides "this is a real opportunity".
2. **SavingsOpportunity records** — persisted locally for Unit 4 to act on.
3. **Notification fan-out** — email + Telegram, each channel independent.

No browser automation, no LLM calls. Credentials come from Unit 1 config/env and alerts
go directly to user-owned services (US-013 — no BookSaver relay).

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| **SavingsOpportunity** (aggregate root) | `opportunityId`, `bookingId`, `checkId`, `baselinePrice` (Money), `livePrice` (Money), `amountSaved` (Money), `percentSaved` (Decimal), `validatedAt`, `notifiedAt` (nullable) | Only created when the gate passes AND live < baseline in the same currency; `amountSaved = baseline − live` (always positive); immutable except `notifiedAt`, set once after notification fan-out |

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| **EquivalenceVerdict** | `equivalent` (bool), `rejectionReason` (nullable enum: `dates_differ`, `property_differs`, `room_differs`, `not_refundable`, `refundability_unknown`) | Exactly one rejection reason when not equivalent |
| **SavingsSummary** | `amountSaved` (Money), `percentSaved` (Decimal, 2dp) | Derived, never stored independently of the opportunity |

## Equivalence Rules (US-008) — the gate

| Extracted field | Rule |
|-----------------|------|
| check-in / check-out | If extracted and ≠ booking's dates → **reject** (`dates_differ`). If absent → pass (the checked page is the booking's own manage page; absence is non-contradiction, not mismatch) |
| property name | If extracted and ≠ booking's property (case-insensitive) → **reject** (`property_differs`). Absent → pass |
| room label | If extracted and ≠ booking's room type (case-insensitive) → **reject** (`room_differs`). Absent → pass |
| refundability | `is_refundable = false` → **reject** (`not_refundable`). `is_refundable = None` (not extracted) → **reject** (`refundability_unknown`) — refundability must be positively confirmed, per the story: "refundable policy absent per extraction → reject" |

> Refundability is the only field where absence rejects: US-008 explicitly demands the
> cheaper offer be *confirmed* refundable; equivalence fields default to pass because the
> monitored page is the reservation's own page.

## Price Rule (US-007)

| Condition | Outcome |
|-----------|---------|
| live.currency ≠ baseline.currency | No opportunity (logged `currency_mismatch`) — never compare across currencies |
| live < baseline (strict) | Opportunity created |
| live ≥ baseline | No opportunity, no alert |

## Domain Events

| Event | Trigger | Payload |
|-------|---------|---------|
| **SavingsDetected** | Gate passed and live < baseline | `opportunityId`, `bookingId`, `baseline`, `live`, `amountSaved`, `percentSaved` |
| **OfferRejected** | Gate failed or price not lower | `bookingId`, `checkId`, `reason` |
| **NotificationSent** | A channel delivered successfully | `opportunityId`, `channel` |
| **NotificationFailed** | A channel raised an error | `opportunityId`, `channel`, `error` — other channels unaffected |

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| **EquivalenceGate** | `evaluate(booking, checkResult) -> EquivalenceVerdict` | none (pure) |
| **SavingsDetector** | `detect(booking, checkResult) -> SavingsOpportunity \| None` — applies gate then price rule | `EquivalenceGate` (pure) |
| **NotificationDispatcher** (application) | `dispatch(opportunity, booking) -> list[ChannelOutcome]` — renders message, attempts every configured channel, logs failures, never raises | `Notifier` port (per channel) |

## Ports (new)

| Port | Operations | Adapters |
|------|------------|----------|
| **Notifier** | `send(subject: str, body: str) -> None` (raises on failure), `channel_name -> str` | `SmtpEmailNotifier` (stdlib smtplib), `TelegramNotifier` (stdlib urllib → Bot API) |
| **SavingsRepository** | `add(opportunity) -> None`, `mark_notified(opportunityId, at) -> None`, `list_for_booking(bookingId) -> list[SavingsOpportunity]`, `get(opportunityId) -> SavingsOpportunity \| None` | SQLite (v3 migration) |

## Ubiquitous Language Additions

| Term | Meaning |
|------|---------|
| **Gate** | The equivalence + refundability check every candidate offer must pass before price comparison |
| **Opportunity** | A validated, persisted savings finding: cheaper, equivalent, confirmed refundable |
| **Channel** | One notification transport (email or Telegram); channels are independent |
| **Rebook pointer** | The CLI command included in alerts that starts Unit 4's guided rebook |

## Forward References

- Unit 4 reads `SavingsOpportunity` via `SavingsRepository.get()` when the user starts a
  guided rebook (`booksaver rebook <opportunity-id>`).
