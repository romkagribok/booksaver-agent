---
id: 002-maintain-recognizable-usernames
unit: 001-invite-first-access
intent: 009-invite-first-sharing
status: complete
priority: must
created: 2026-07-19T02:34:21Z
assigned_bolt: 021-invite-first-access
implemented: true
---

# Story: Maintain Recognizable Telegram Usernames

**Global story ID**: US-063

## User Story

**As a** BookSaver owner
**I want** admitted users labeled by their current Telegram username when available
**So that** I can recognize whom I am managing without exposing numeric Telegram IDs

## Acceptance Criteria

- [ ] Message and callback updates carry optional `from.username` to the access boundary.
- [ ] Successful owner linkage, invite redemption, and later active interactions persist or refresh it.
- [ ] A later authorized update without a username clears the stored display metadata.
- [ ] Usernames are stored canonically without `@` and persistence writes occur only on change.
- [ ] Unknown, invalid-code, expired/used-code, and revoked traffic never creates or refreshes it.
- [ ] `/admin users` and revoke/purge pickers prefer `@username` and otherwise use an internal
  `User #N (no @username)` fallback without showing Telegram IDs.
- [ ] Authorization continues to use only the stable numeric Telegram user ID.
- [ ] Fresh schema v9 and idempotent v8-to-v9 migration preserve all existing user-scoped data.

## Technical Notes

- Add one nullable, non-unique username column; Telegram handles are mutable/recyclable metadata.
- Keep username rendering in an owner-administration helper and out of logs/traces/user-facing lists.
- Purge removes it with the user row; revoke retains the last authorized value.

## Dependencies

### Requires

- Bolt 009 user repository, stable-ID authorization, and purge behavior.

### Enables

- Recognizable revoke/purge selection in US-065.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User never configured a Telegram username | Show internal user number and `no @username` |
| User changes username | Next authorized message/callback replaces the snapshot |
| User removes username | Next authorized update clears the snapshot |
| Username is recycled to another account | Stable numeric IDs keep authorization and rows distinct |

## Out of Scope

- Username login, username uniqueness, or historical handle tracking.
- Full names, phone numbers, bios, or other Telegram profile fields.
