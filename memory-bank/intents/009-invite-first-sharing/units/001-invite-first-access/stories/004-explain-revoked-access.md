---
id: 004-explain-revoked-access
unit: 001-invite-first-access
intent: 009-invite-first-sharing
status: complete
priority: must
created: 2026-07-19T02:34:21Z
assigned_bolt: 021-invite-first-access
implemented: true
---

# Story: Explain Revoked Access

**Global story ID**: US-065

## User Story

**As a** previously invited BookSaver user
**I want** a clear explanation when my access is revoked
**So that** the bot does not appear silently broken

## Acceptance Criteria

- [ ] Revocation commits before any outbound notification is attempted.
- [ ] When the user has a Telegram identity, successful revocation makes one immediate best-effort
  send of exactly `You no longer have access to this bot.` outside the generic outbound limiter.
- [ ] Owner confirmation accurately reports whether target delivery succeeded, failed, or was
  unavailable without undoing revocation.
- [ ] The first eligible later revoked-user command per refusal window receives the exact same message.
- [ ] A later revoked-user callback is acknowledged with the exact same explanation.
- [ ] Unknown users and unusable invite attempts retain the generic private-bot refusal.
- [ ] Notification failure is logged without identity metadata and cannot undo revocation.
- [ ] Repeat-command refusal limits continue to apply; every revoked callback is acknowledged.

## Technical Notes

- Access decisions must distinguish revoked from unknown internally while preserving the generic
  external response for unknown users.
- The repository commit is the source of truth; Telegram delivery is best effort afterward.

## Dependencies

### Requires

- US-063 owner-recognizable user records.
- US-064 fixed invite-first access decision path.

### Enables

- Understandable, testable offboarding without user-state disclosure.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Revoked row lacks Telegram identity | Owner confirmation succeeds; no proactive send is attempted |
| Telegram proactive send fails | User stays revoked and owner receives an accurate confirmation |
| Revoked user repeatedly sends commands | Exact message remains subject to existing refusal rate limit |
| Unknown sender mimics a revoked command | Receives only the generic private-bot refusal |

## Out of Scope

- Restoring access, appeal workflows, or deleting retained user data automatically.
