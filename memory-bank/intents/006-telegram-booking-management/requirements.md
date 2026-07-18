---
intent: 006-telegram-booking-management
phase: inception
status: complete
created: 2026-07-18T22:40:07.000Z
updated: 2026-07-18T23:19:09Z
---

# Requirements: Telegram Booking Management

## Intent Overview

Let an authorized Telegram user correct or remove one of their own monitored bookings without
copying a UUID into a VPS terminal. Telegram supplies button-selectable booking and action choices;
values that cannot be enumerated safely are collected through validated chat dialogs.

## Functional Requirements

### FR-1: Discover booking management commands

- **Description**: Publish and document `/editbooking` and `/deletebooking` alongside the existing
  Telegram commands.
- **Acceptance Criteria**:
  - Both commands appear in the native private-chat and owner command menus and in `/help`.
  - Command definitions remain sourced from the shared command catalog.
  - Existing command publication degradation behavior remains unchanged.
- **Priority**: Must
- **Related Stories**: US-048

### FR-2: Edit a caller-owned booking interactively

- **Description**: `/editbooking` must offer the caller's active bookings as buttons, then offer the
  editable field groups as buttons. Free-form replacement values may use a dialog and must be
  validated through the existing domain value objects before persistence.
- **Acceptance Criteria**:
  - The booking picker contains only active bookings owned by the caller and uses recognizable
    property/date labels.
  - Editable groups cover property/reference, stay dates, room type, baseline price, refund-policy
    detail, occupancy, and confirmation ID.
  - Selecting a group starts only the minimum free-form prompts needed for that group.
  - Completion re-resolves current ownership, refuses stale/foreign/deleted bookings without
    disclosure, preserves untouched fields and booking identity, and stores an aggregate satisfying
    all existing booking invariants.
  - `/editbooking <booking-id-or-unique-prefix>` remains available as a typed shortcut to the field
    picker.
- **Priority**: Must
- **Related Stories**: US-049

### FR-3: Delete a caller-owned booking with explicit confirmation

- **Description**: `/deletebooking` must offer the caller's active bookings as buttons and require a
  separate Confirm tap immediately before permanent deletion.
- **Acceptance Criteria**:
  - Selection and confirmation callbacks re-authorize and re-resolve ownership at action time.
  - The confirmation message names the booking and explains that booking-linked check history,
    traces, savings, and rebook history will also be deleted.
  - Cancel leaves all data unchanged; replayed, malformed, stale, foreign, or deleted selections
    perform no mutation and disclose no foreign data.
  - `/deletebooking <booking-id-or-unique-prefix>` remains available as a typed shortcut to the
    confirmation screen.
- **Priority**: Must
- **Related Stories**: US-050

### FR-4: Preserve monitoring and persistence integrity

- **Description**: Booking updates and deletion must use explicit persistence operations that remain
  compatible with the daemon scheduler and existing relational data.
- **Acceptance Criteria**:
  - An edit retains the same booking ID, owner, registration timestamp, active status, check history,
    and rebook audit history while future scheduler reads observe the new monitoring values.
  - Existing savings opportunities are invalidated atomically on edit because they were evaluated
    against the previous dates, room, occupancy, refund policy, or baseline.
  - A deletion removes the booking and every booking-scoped dependent row in one transaction.
  - Repository mutations report missing targets and confirmation-ID conflicts predictably.
  - Edit/delete refuses a booking with a non-terminal guided-rebook session so an active safety
    workflow cannot lose or change its aggregate underneath the worker.
  - No database migration or runtime dependency is introduced.
- **Priority**: Must
- **Related Stories**: US-051

## Non-Functional Requirements

### Security and Privacy

- **Ownership enforcement**: 100% of selection, dialog-completion, and confirmation mutations reload
  the active user and selected booking from caller-scoped persistence.
- **Foreign disclosure/action**: zero foreign booking labels, values, or mutation results.
- **Destructive gate**: zero booking deletions without a distinct inline Confirm callback.

### Reliability and Compatibility

- All callback payloads remain within Telegram's 64-byte UTF-8 limit and are acknowledged.
- Existing registration, checks, savings, rebook, admin, scheduler, and typed command tests remain
  passing.
- Ruff, mypy, focused Telegram/persistence tests, and the full pytest suite are clean.

### Usability

- Normal edit/delete flows require no booking UUID or field-name typing.
- Every input derived from BookSaver state or a closed action set is button-selectable.
- Only replacement values such as names, dates, prices, references, and counts require chat text.

## Constraints

- Use the existing `DialogManager`, callback router, Telegram client, SQLite repositories, domain
  value objects, and gateway access guard.
- BookSaver continues to support Booking.com hotels and refundable bookings only.
- Do not alter guided-rebook confirmation authority or perform any Booking.com cancellation.
- Add no schema, service, process, or runtime dependency.

## Assumptions and Decisions

- “Delete booking” means permanent local deletion of the monitored booking and its local dependent
  history, not cancellation of the Booking.com reservation.
- Edits mutate one coherent field group at a time; dates and occupancy are grouped so no transient
  invalid aggregate can be stored.
- Edit is not destructive and persists after its validated free-form dialog completes. Delete alone
  requires the explicit inline confirmation requested by the product owner.
- The product owner's parallel-work direction authorizes continuous inception and construction-stage
  progression, with one compressed validation immediately before Bolt 017 closure.

## Scope Exclusions

- Editing or cancelling the reservation on Booking.com.
- Restoring deleted BookSaver history.
- Bulk edit/delete, archived-booking management, or changing booking ownership.
- Inline Telegram date-picker or Mini App UI.
