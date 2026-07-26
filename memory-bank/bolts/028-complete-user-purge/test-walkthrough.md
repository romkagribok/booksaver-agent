---
stage: test
bolt: 028-complete-user-purge
created: 2026-07-26T21:23:28Z
---

## Test Report: Complete User Purge

### Summary

- **Focused tests**: 92/92 passed across the integrated purge and remote-auth boundary
- **Full tests**: 883/883 passed
- **Ruff**: Clean across `src` and `tests`
- **mypy**: Clean across 93 source files
- **AI-DLC artifact validator**: 0 issues
- **AI-DLC status integrity**: 0 inconsistencies after the deterministic construction-state repair
- **Diff hygiene**: Clean

### Test Files

- [x] `tests/unit/test_remote_auth.py` - Target-scoped cancellation, cancellation-wins, and
  capture-wins synchronization.
- [x] `tests/unit/test_encrypted_user_sessions.py` - Target isolation, missing-session behavior,
  and authoritative locked deletion.
- [x] `tests/unit/telegram/test_admin_commands.py` - Typed and inline confirmations, cleanup order,
  missing sessions, owner protection, and storage failure handling.
- [x] `tests/unit/telegram/test_gateway.py` - Production composition from admin purge through
  encrypted-session and SQLite deletion.
- [x] `tests/unit/test_cli_user_sessions.py` - Existing targeted CLI deletion semantics remain
  intact.
- [x] Full `tests/` suite - Cross-component regression.

### Acceptance Criteria Validation

- ✅ **Remove all target state**: Typed and inline confirmed purge cancel active login, delete the
  target encrypted session, and then execute the existing database cascade.
- ✅ **Treat missing sessions as success**: A missing encrypted file still produces a durable,
  non-secret revocation marker and purge continues.
- ✅ **Preserve other users**: Session and database operations remain explicitly target-scoped.
- ✅ **Fail safely on storage errors**: An `OSError` prevents SQLite purge and returns a generic
  retry response without exposing paths or secrets.
- ✅ **Reconcile SQLite failure**: A database error after revocation reports the durable partial
  state and a safe retry without exposing database details.
- ✅ **Close the capture race**: Cancellation uses the same manager lock as terminal cookie capture;
  either cancellation suppresses persistence or purge deletes the already-captured file.
- ✅ **Close the operator-import race**: Every session save checks the permanent revocation marker
  under the same owner lock, so a prevalidated import cannot write after purge revocation.
- ✅ **Preserve worker ownership**: Cancellation signals the attempt and leaves browser teardown to
  the existing worker path.

### Issues Found

- The initial full gate exposed an outdated CLI expectation that missing deletion would not create
  the session directory. Independent review then showed that locked deletion alone still allowed an
  already-validated operator import to write after the lock was released. The final purge operation
  writes a permanent non-secret revocation marker under the lock, and repository tests prove future
  saves are rejected while other users remain unaffected.
- Status integrity found the new intent still marked `units-defined` after construction began. The
  framework's deterministic `--fix` path aligned it to `construction` and logged the repair.

### Remaining Acceptance

Real Telegram owner testing should confirm both typed and inline purge messages and verify that a
purged user must reconnect. That requires a deployed build and remains held for explicit Git and
deployment approval.
