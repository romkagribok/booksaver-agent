---
id: 001-discover-applicable-commands-natively
unit: 001-interactive-command-navigation
intent: 005-telegram-command-navigation
status: complete
priority: must
created: 2026-07-18T22:14:33.000Z
assigned_bolt: 016-interactive-command-navigation
implemented: true
---

# Story: Discover Applicable Commands Natively

**Global story ID**: US-043

## User Story

**As an** authorized Telegram user
**I want** BookSaver commands to appear in Telegram's native command menu
**So that** I can discover and select commands without remembering their names

## Acceptance Criteria

- [ ] **Given** the bot starts, **When** Telegram accepts metadata publication, **Then** private chats
  receive the supported non-admin commands and the owner chat receives the owner list including admin.
- [ ] **Given** command handlers or help change, **When** definitions are reviewed, **Then** one
  authoritative catalog supplies command publication and help text.
- [ ] **Given** Telegram rejects or cannot receive `setMyCommands`, **When** the bot starts, **Then**
  the failure is logged without stopping long polling.

## Technical Notes

- Use the existing stdlib client and Telegram command scopes.
- Keep command names lowercase and descriptions within Telegram limits.

## Dependencies

### Requires

- Intent 003 Telegram gateway and US-040 complete help list.

### Enables

- US-045 and US-046 discoverability.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Owner scope publication fails after default succeeds | Bot still starts; failure is logged |
| Invited user types `/admin` manually | Existing owner authorization refuses it |

## Out of Scope

- Localized command descriptions.
- Telegram Mini App menu buttons.
