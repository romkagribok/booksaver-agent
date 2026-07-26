---
id: 001-remove-encrypted-authentication-state
unit: 001-complete-user-purge
intent: 015-authentication-boundary-hardening
status: complete
priority: must
created: 2026-07-26T19:41:07.000Z
assigned_bolt: 028-complete-user-purge
implemented: true
---

# Story: Remove Encrypted Authentication State During Purge

## User Story

**As a** BookSaver owner
**I want** confirmed purge to remove a user's encrypted Booking.com session
**So that** destructive offboarding does not retain authentication data outside SQLite

## Acceptance Criteria

- [ ] **Given** the target has an encrypted session, **When** typed or inline purge is confirmed,
  **Then** the session and all existing database-scoped target data are removed.
- [ ] **Given** the target has no encrypted session, **When** purge is confirmed, **Then** purge
  still succeeds.
- [ ] **Given** another user has an encrypted session, **When** the target is purged, **Then** the
  other session remains unchanged.
- [ ] **Given** session deletion fails, **When** purge is attempted, **Then** database state is
  retained and the owner receives a safe failure response.
- [ ] **Given** an operator import validated the target before purge, **When** it attempts to save
  afterward, **Then** the permanent revocation marker rejects the write.
- [ ] **Given** revocation succeeds but SQLite cleanup fails, **When** the owner is notified,
  **Then** the message says authentication remains revoked and directs a safe purge retry.

## Technical Notes

- Inject the session-deletion boundary from the configured data directory.
- Revoke under the repository's per-owner lock before calling the SQLite purge. The non-secret
  marker must be checked by every subsequent session save.

## Dependencies

### Requires

- Existing confirmed `/admin purge` and encrypted per-user session repository.

### Enables

- US-098 race-safe remote-auth cancellation.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Session file disappears before lock acquisition | Treat as already deleted |
| Owner selected as target | Existing owner guard rejects before cleanup |

## Out of Scope

- Secure erase guarantees for filesystem blocks or backups.
