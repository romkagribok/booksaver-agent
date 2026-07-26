---
stage: implement
bolt: 028-complete-user-purge
created: 2026-07-26T21:18:54.000Z
---

## Implementation Walkthrough: Complete User Purge

### Summary

Confirmed Telegram purge now coordinates active-login cancellation, encrypted Booking.com session
revocation/deletion, and the existing database cascade. Storage failures retain database state and
produce a safe retry message instead of a false completion. A permanent non-secret marker prevents
an already-validated operator import from recreating the purged session afterward.

### Structure Overview

The remote-auth application manager owns target-scoped cancellation and its capture race. The
encrypted-session repository owns serialized file deletion. Telegram composition injects those two
boundaries into the existing owner-only admin handler, which preserves the typed and inline
confirmation controls.

### Completed Work

- [x] `src/booksaver/application/remote_auth.py` - Adds target-scoped cancellation under the
  terminal capture lock.
- [x] `src/booksaver/infrastructure/persistence/encrypted_session_store.py` - Serializes deletion
  and permanent revocation under the same owner lock checked by every session save.
- [x] `src/booksaver/infrastructure/telegram/admin_commands.py` - Orders cancellation, session
  revocation, and database purge with safe storage and SQLite failure reconciliation.
- [x] `src/booksaver/infrastructure/telegram/gateway.py` - Wires configured session storage and the
  optional remote-auth manager into admin purge.
- [x] `tests/unit/test_remote_auth.py` - Covers cancellation-wins and capture-wins synchronization.
- [x] `tests/unit/test_encrypted_user_sessions.py` - Covers locked delete ordering and isolation.
- [x] `tests/unit/telegram/test_admin_commands.py` - Covers confirmation, cleanup order, missing
  sessions, owner protection, storage failure, and inline callbacks.
- [x] `tests/unit/telegram/test_gateway.py` - Covers production composition from admin command to
  session file and database deletion.

### Key Decisions

- **Cancel before delete**: The manager lock ensures either cancellation suppresses capture or purge
  observes capture completion and deletes its result.
- **Delete session before SQLite**: A file failure leaves a retryable user record instead of
  claiming complete removal with retained authentication data.
- **Persist a revocation marker**: A non-secret local-user tombstone makes the purge boundary
  durable against operator imports that validated before the SQLite row was removed.
- **Make partial completion explicit**: SQLite failure after revocation keeps the safe marker and
  tells the owner to retry the idempotent confirmed purge.
- **Worker-owned teardown**: Target cancellation signals the existing worker and does not release
  browser resources early.

### Deviations from Plan

The implementation added a permanent non-secret revocation marker beyond the initial deletion-only
plan. Independent review showed locking deletion alone could not stop an operator import that had
already validated the target and was waiting to save. Ordinary CLI session deletion remains
reversible; only confirmed user purge installs the marker.

### Dependencies Added

None.

### Developer Notes

The filesystem and SQLite cannot share one atomic transaction. The chosen ordering deliberately
prefers safe partial failure: a user may temporarily remain locally revoked if SQLite purge fails,
but a successful purge never leaves or permits recreation of the encrypted session.
