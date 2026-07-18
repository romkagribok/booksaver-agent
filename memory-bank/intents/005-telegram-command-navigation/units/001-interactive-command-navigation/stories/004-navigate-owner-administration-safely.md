---
id: 004-navigate-owner-administration-safely
unit: 001-interactive-command-navigation
intent: 005-telegram-command-navigation
status: complete
priority: must
created: 2026-07-18T22:14:33.000Z
assigned_bolt: 016-interactive-command-navigation
implemented: true
---

# Story: Navigate Owner Administration Safely

**Global story ID**: US-046

## User Story

**As the** BookSaver owner
**I want** admin actions and applicable inputs presented as buttons
**So that** I can manage access without memorizing user IDs or confirmation syntax

## Acceptance Criteria

- [ ] **Given** I send `/admin` as owner, **When** the menu renders, **Then** users, invite, revoke,
  purge, and mode actions are selectable.
- [ ] **Given** revoke or purge needs a target, **When** I choose it, **Then** only non-owner users are
  offered and the selected user is reloaded before mutation.
- [ ] **Given** revoke, purge, or mode would mutate state, **When** I select it, **Then** Confirm and
  Cancel buttons appear and only Confirm executes the operation.
- [ ] **Given** a non-owner or revoked user sends/forges an admin callback, **When** it arrives, **Then**
  no admin information or mutation is produced.
- [ ] **Given** I prefer typed administration, **When** I use existing `/admin ...` syntax, **Then** it
  remains compatible.

## Technical Notes

- Recheck `AccessControl.is_owner` in every admin callback.
- Edit menu messages to keep the interaction compact.

## Dependencies

### Requires

- US-044 callback router and existing US-028 admin operations.

### Enables

- Safe identifier-free owner administration.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| No non-owner users exist | Clear empty state plus Back button |
| Target is purged/revoked before confirmation | Re-resolve and report stale/unchanged safely |
| Owner target is forged | Refuse the action |

## Out of Scope

- Changing persistent config through the admin menu.
