---
stage: design
bolt: 023-post-rebook-monitoring
created: 2026-07-19T19:54:15Z
---

# Technical Design: Post-Rebook Monitoring

## Architecture Pattern

Retain the project's hexagonal, single-process architecture. Telegram owns transient conversation
presentation; an application module owns outcome/fact commands; an additive repository port defines
the atomic transition; SQLite owns concurrency, ownership, and relational consistency. No Booking.com
browser action or monitor pipeline is added.

## Layer Structure

```text
Telegram rebook adapter
  ├─ capture completed/abandoned/unreported outcomes
  ├─ acknowledge actual-fact answers through DialogManager
  └─ render final monitoring disposition
             │
             ▼
Post-rebook application service
  ├─ validate/canonicalize ReplacementFacts
  ├─ construct archive/activation commands
  └─ translate safe rejection categories
             │
             ▼
PostRebookRepository port
             │
             ▼
SQLite adapter (BEGIN IMMEDIATE)
  ├─ revalidate active user + ownership
  ├─ verify session/opportunity/handoff + source snapshot
  ├─ update status or replacement facts
  ├─ delete stale savings
  └─ append rebook disposition event
```

## Telegram Conversation Contract

1. Existing outcome prompts independently record cancellation and replacement as completed,
   abandoned, or unreported.
2. On reported cancellation completion, archive reconciliation occurs before any replacement dialog.
   This durable fail-safe survives `/cancelflow`, timeout, or daemon restart.
3. On reported replacement completion, start a `DialogDefinition` with:
   - actual confirmation ID;
   - same-property Booking.com property URL;
   - actual all-in `amount CURRENCY`;
   - final yes/no summary.
4. Each dynamic prompt begins by acknowledging the prior accepted answer.
5. Final yes calls activation; final no leaves the current safe disposition and explains it.
6. Messages enter through the existing private-chat/access guard before `DialogManager`.

## Application Contracts

### `ReplacementFacts`

- `confirmation_id: ConfirmationId`
- `property_ref: str` (canonical Booking.com property URL)
- `actual_total: Money`

### `PostRebookContext`

- `user_id`, `session_id`, `opportunity_id`
- immutable `source_booking` snapshot
- cancellation outcome for final duplicate/unknown warning

### `PostRebookRepository`

- `archive_cancelled_source(context) -> ReconciliationResult`
- `activate_replacement(context, facts) -> ReconciliationResult`

Results distinguish applied, already-applied, unchanged, access-lost, stale, and conflict without
revealing foreign record identity.

## Persistence Design

No schema migration. Add atomic operations to the SQLite booking adapter/port.

### Guard query

Within `BEGIN IMMEDIATE`:

- Load the active user by local user ID.
- Load booking and assert `bookings.user_id` matches.
- Load session and assert booking/opportunity linkage.
- Require a terminal state and the appropriate persisted Telegram handoff event (`cancel` or `book`).
- Compare current monitored fields against the source snapshot. Activation also accepts the source
  archived by this same session; retries accept an already-identical replacement by this session.
- Let the unique confirmation constraint enforce global uniqueness; map conflicts generically.

### Archive write

- Set `bookings.status = 'archived'` only.
- Delete all `savings_opportunities` for the booking.
- Append an `action_executed` rebook event with disposition `source_archived`.

### Activation write

- Update confirmation ID, canonical property reference, baseline amount/currency, and status `active`.
- Preserve property name, stay dates, room, refundability, occupancy, booking ID, registration time,
  owner, checks, traces, sessions, and prior events.
- Delete all `savings_opportunities` for the booking.
- Append an `action_executed` event with disposition `replacement_active` and actual amount/currency.

## Property Reference Validation

- Require HTTPS and a host equal to `booking.com` or ending `.booking.com`.
- Require a `/hotel/` property path.
- Canonicalize to `https://www.booking.com{path}` with no query or fragment.
- If the source reference has a Booking.com `/hotel/` path, normalized paths must match. If the
  legacy source is a non-URL reference, the validated Booking.com property URL becomes authoritative.

## Outcome Matrix Implementation

- Collect both outcomes before final messaging.
- If cancellation is completed, invoke archive immediately and retain that result.
- If replacement is completed and a book handoff exists, start actual-facts dialog.
- Otherwise render:
  - archived/no monitored booking when cancellation completed;
  - original still monitored when cancellation was abandoned/unreported.
- Activation final message adds a duplicate/unknown old-cancellation warning where applicable.

## Security Design

- No owner bypass: local user must own the booking.
- Access is checked at prompt/dialog start and transaction time.
- Revoked messages are rejected before dialogs by the gateway; the transaction provides the final race guard.
- Session and handoff validation prevents crafted direct dialog invocation.
- Conflict/rejection messages do not identify another user's confirmation or booking.
- Audit excludes Telegram message bodies, chat IDs, and URL query parameters.

## NFR Implementation

- **Atomicity**: Explicit immediate SQLite transaction covers guards, booking, savings, and event.
- **Idempotence**: Same-session archive/activation retry returns already applied without duplicate event.
- **Restart safety**: Archive occurs before transient replacement detail collection.
- **Compatibility**: Existing Booking, rebook state machine, monitor, and schema remain unchanged.
- **Testability**: Pure URL/fact validators and outcome result rendering; fake DialogManager/client plus real SQLite transaction tests.

## Files Planned

- `src/booksaver/application/post_rebook.py` — commands, facts, results, validation/service.
- `src/booksaver/application/ports.py` — additive post-rebook repository protocol.
- `src/booksaver/infrastructure/persistence/sqlite_store.py` — atomic archive/activation implementation.
- `src/booksaver/infrastructure/telegram/rebook_gate.py` — outcome capture, details dialog, final UX.
- `src/booksaver/infrastructure/telegram/gateway.py` — inject shared `DialogManager` into rebook registration.
- Focused application, Telegram, and integration tests.
