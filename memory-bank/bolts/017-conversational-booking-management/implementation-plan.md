---
stage: plan
bolt: 017-conversational-booking-management
created: 2026-07-18T22:40:07Z
---

# Implementation Plan: Conversational Booking Management

## Objective

Add safe Telegram booking correction and permanent local deletion without weakening user scoping,
domain validation, scheduler reads, or relational consistency.

## Deliverables

- Shared command catalog entries and gateway registration.
- One booking-management Telegram module with owned booking pickers, edit field picker, targeted
  dialogs, delete warning, Confirm/Cancel buttons, and typed shortcuts.
- Booking repository port and SQLite operations for whole-aggregate update and transactional cascade
  deletion.
- Unit/integration tests for validation, scoping, callbacks, persistence, catalog, and gateway wiring.
- Implementation and test walkthroughs.

## Dependencies

- Existing command and callback routers, `DialogManager`, Telegram client, access guard, repositories,
  and domain value objects.
- SQLite schema v8 booking-linked tables.
- No new package, schema migration, external API, or background component.

## Technical Approach

Resolve user ownership from Telegram identity at every picker, callback, and dialog-completion seam.
Use compact full-UUID callbacks and never trust labels. Construct edited aggregates by replacing only
the chosen validated field group, then persist all editable columns while leaving identity and owner
untouched. Atomically invalidate savings evaluated against the prior aggregate while retaining check
and rebook audit history. Delete linked rows in dependency order inside one SQLite transaction. Keep
typed IDs and unique displayed prefixes as shortcuts into the same callback-rendering behavior.
Refuse either mutation while a non-terminal guided-rebook session is using the booking.

## Acceptance Criteria

- [x] Catalog/help/native menus expose both commands.
- [x] Normal edit/delete flows require no identifier or field-name entry.
- [x] Edit groups validate and preserve all untouched aggregate state.
- [x] Foreign, stale, malformed, ambiguous, or replayed selections do not disclose or mutate data.
- [x] Delete requires distinct confirmation and removes all linked local rows atomically.
- [x] Scheduler reads observe edits and omit deletions.
- [x] Existing typed behavior and all project quality gates remain clean.
