---
stage: implement
bolt: 017-conversational-booking-management
created: 2026-07-18T22:58:23Z
---

# Implementation Walkthrough: Conversational Booking Management

## Summary

BookSaver now exposes discoverable Telegram edit/delete booking commands with caller-owned booking
selection, selectable edit groups, validated replacement-value dialogs, and explicit permanent-delete
confirmation. Persistence gained whole-aggregate update and transactional cascade deletion while
protecting active guided-rebook sessions and stale savings safety.

## Structure Overview

The Telegram inbound adapter owns presentation, transient callback/dialog state, and repeated
ownership resolution. The application layer owns mutation intent and confirmation uniqueness. The
SQLite adapter owns atomic row updates, savings invalidation, active-rebook exclusion, and deletion
ordering. Existing domain value objects remain the only validators for stored booking values.

## Completed Work

- [x] `src/booksaver/infrastructure/telegram/booking_management.py` - Caller-scoped booking and
  field pickers, edit dialogs, typed shortcuts, callback handling, and confirmed deletion.
- [x] `src/booksaver/infrastructure/telegram/command_catalog.py` - Native/help definitions for the
  two new commands.
- [x] `src/booksaver/infrastructure/telegram/gateway.py` - Shared router/dialog/client wiring for the
  booking-management command family.
- [x] `src/booksaver/application/manage_booking.py` - Application mutation functions and
  confirmation-ID conflict validation.
- [x] `src/booksaver/application/ports.py` - Explicit booking update/delete repository contract.
- [x] `src/booksaver/infrastructure/persistence/sqlite_store.py` - Identity-preserving update,
  stale-savings invalidation, active-rebook guard, and atomic dependent-data deletion.
- [x] `tests/unit/telegram/test_booking_management.py` - Interactive, validation, scoping, stale,
  replay, typed, cancellation, confirmation, and rebook-concurrency coverage.
- [x] `tests/integration/test_persistence.py` - Update, uniqueness, scheduler-read, savings, audit,
  cascade, missing-target, and active-rebook persistence coverage.
- [x] `tests/unit/telegram/test_command_catalog.py` - Native/help discoverability coverage.

## Key Decisions

- **Permanent local deletion**: Delete removes the BookSaver row and linked local history but never
  attempts to cancel a Booking.com reservation; the warning states this explicitly.
- **One edit group per dialog**: Dates and occupancy remain coherent groups, while all groups are
  selectable buttons and only replacement values use text.
- **Invalidate savings after any edit**: The schema cannot mark an offer stale, so opportunities
  evaluated against the former aggregate are deleted while checks and rebook audit history remain.
- **Block active rebook mutations**: Edit/delete refuses while a non-terminal guided-rebook session
  is using the booking, preventing a guarded worker from losing or changing its aggregate.
- **No edit confirmation**: A validated edit persists on dialog completion; only permanent deletion
  has the explicitly requested separate inline confirmation.

## Deviations from Plan

The implementation added explicit stale-savings invalidation and a non-terminal guided-rebook guard
after the persistence safety audit identified actionable stale offers and worker races. Both tighten
FR-4 without expanding the external capability.

## Dependencies Added

None.

## Developer Notes

Callback payloads use full UUIDs and remain below Telegram's 64-byte limit. Labels are presentation
only; every callback and dialog completion reloads caller-scoped state from SQLite.
