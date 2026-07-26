---
stage: plan
bolt: 028-complete-user-purge
created: 2026-07-26T19:45:19.000Z
---

## Implementation Plan: Complete User Purge

### Objective

Make confirmed Telegram purge remove encrypted Booking.com authentication state and serialize
destructive offboarding against an in-flight remote-auth capture.

### Deliverables

- A target-scoped remote-auth cancellation operation using the manager's existing capture lock.
- Permanent session revocation and deletion performed under the repository's per-owner filesystem
  lock.
- Typed and inline admin purge paths wired to cancellation and session deletion.
- Fail-closed storage error handling that preserves database state and reports no false success.
- Explicit, retryable reconciliation guidance if SQLite cleanup fails after durable revocation.
- Targeted race, isolation, failure, command, and callback tests.

### Dependencies

- `RemoteAuthenticationManager`: owns the active attempt and terminal capture synchronization.
- `EncryptedUserSessionRepository`: owns encrypted per-user session files and locks.
- `SqliteUserRepository`: retains the existing database cascade and owner guard.
- Telegram bot composition: already receives the optional remote-auth manager and configured data
  directory.

### Technical Approach

Add a manager operation that, under its existing re-entrant lock, cancels a matching non-terminal
attempt without releasing lifecycle resources early. Add a repository purge-revocation operation
that deletes the session and writes a non-secret permanent marker under the same owner lock checked
by every session save. Inject cancellation and session revocation callbacks into admin command
registration and both confirmed purge entry points.

The confirmed operation orders work as: cancel active capture, delete the encrypted session, then
purge SQLite state. Missing attempts and sessions are successful no-ops. An `OSError` deleting the
session aborts before SQLite mutation, logs only safe context, and returns a retryable owner message.
If SQLite cleanup fails after revocation, retain the durable marker, report the partial state without
database details, and direct the owner to retry the idempotent confirmed purge.

### Acceptance Criteria

- [ ] Both typed and inline-confirmation purge remove the target session and database state.
- [ ] Another user's session remains unchanged.
- [ ] A successful runner result cannot persist after cancellation wins.
- [ ] A capture that wins first is removed by the following session deletion.
- [ ] An operator import that validated first cannot write after revocation.
- [ ] Storage deletion failure retains the user/database state and does not claim success.
- [ ] Owner protection and explicit confirmation remain unchanged.
