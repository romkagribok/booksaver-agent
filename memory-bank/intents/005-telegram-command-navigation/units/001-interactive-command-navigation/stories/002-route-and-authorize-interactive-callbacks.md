---
id: 002-route-and-authorize-interactive-callbacks
unit: 001-interactive-command-navigation
intent: 005-telegram-command-navigation
status: complete
priority: must
created: 2026-07-18T22:14:33.000Z
assigned_bolt: 016-interactive-command-navigation
implemented: true
---

# Story: Route and Authorize Interactive Callbacks

**Global story ID**: US-044

## User Story

**As a** BookSaver feature developer
**I want** independent callback families to share a guarded router
**So that** interactive commands can grow without bypassing access control or breaking rebook buttons

## Acceptance Criteria

- [ ] **Given** multiple registered callback prefixes, **When** a callback arrives, **Then** exactly
  the matching handler runs.
- [ ] **Given** a duplicate prefix, **When** gateway wiring registers it, **Then** startup fails locally
  with a clear programming error rather than routing ambiguously.
- [ ] **Given** an unauthorized, unknown, or stale callback, **When** it arrives, **Then** no protected
  handler runs and Telegram receives an acknowledgement.
- [ ] **Given** an existing rebook confirmation button, **When** it is tapped, **Then** its current
  nonce/chat/user verification and confirmation behavior is unchanged.

## Technical Notes

- Keep routing prefix-based and synchronous inside the bot loop.
- Apply access checks before feature dispatch; handlers still enforce entity ownership.

## Dependencies

### Requires

- Intent 003 callback query transport and access control.

### Enables

- US-045 and US-046.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Callback has no registered prefix | Acknowledge as expired; do not crash |
| Revoked invited user taps an old button | Refuse and acknowledge without disclosure |

## Out of Scope

- Persisting callback routes or button sessions.
