---
stage: design
bolt: 024-per-user-booking-sessions
created: 2026-07-19T21:23:00Z
---

# Technical Design: Per-User Booking.com Sessions

## Architecture

Keep the existing synchronous, serialized daemon. Add a user-scoped session port/application service,
an encrypted filesystem repository, scoped CLI operations, and check-admission integration. SQLite
continues to own user/booking identity; secret browser state remains outside SQLite.

## Persistence

- Directory: `{data_directory}/booking_sessions/`, mode 0700.
- File per stable local user ID, mode 0600, containing versioned metadata plus one Fernet token.
- Fernet key is derived/loaded through the existing encryption-secret mechanism; missing/invalid key
  makes authenticated session operations unavailable rather than writing plaintext.
- Temp-file + fsync + atomic replace; rejected import cannot damage the prior bundle.
- Explicit CLI migration maps legacy `session_booking_com.json` to the owner and removes/archive-renames
  it only after successful encrypted write; never auto-shares it.

## Public Contracts

- `AuthenticatedSessionProvider.resolve(user_id) -> Ready(snapshot) | Unavailable(reason)`.
- Snapshot: owner ID, revision UUID, normalized Playwright cookies/storage state, expiry metadata.
- `mark_validated/mark_reauth_required/refresh` require owner + expected revision.
- CLI: `booksaver auth import <file> --telegram-user-id <id>`, `auth status --telegram-user-id <id>`,
  `auth delete --telegram-user-id <id>`, and explicit owner legacy migration.

## Runtime Flow

1. Check coordinator resolves booking owner and active access.
2. Provider resolves/decrypts exactly that owner's ready revision.
3. Browser adapter opens a clean context and restores that snapshot.
4. Journey verifies rendered authentication. Signed-out/ambiguous state invalidates that revision and
   records `auth_required`; no price enters savings.
5. Successful check captures refreshed state and compare-and-replaces only the same revision.
6. Context closes before the next user's state is resolved.

## Compatibility and UI

- Owner-operated CLI is the only cookie-secret intake.
- `/status` may show caller health and owner aggregate counts, never cookie/account metadata.
- Legacy logged-out CLI behavior may remain only for explicitly non-Telegram/local workflows if tests
  prove it cannot be reached by Telegram-owned scheduled or on-demand checks.

## Security and Test Design

- Tests cover encrypted bytes, permissions, atomicity, wrong key, malformed import, legacy migration,
  revision races, owner/invitee isolation, revoked user, missing/expired/signed-out state, context reset,
  redaction, scheduled/on-demand parity, and continued action-guard denial.
