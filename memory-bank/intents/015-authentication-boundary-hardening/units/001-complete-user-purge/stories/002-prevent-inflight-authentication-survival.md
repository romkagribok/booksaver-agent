---
id: 002-prevent-inflight-authentication-survival
unit: 001-complete-user-purge
intent: 015-authentication-boundary-hardening
status: complete
priority: must
created: 2026-07-26T19:41:07.000Z
assigned_bolt: 028-complete-user-purge
implemented: true
---

# Story: Prevent In-Flight Authentication from Surviving Purge

## User Story

**As a** BookSaver owner
**I want** purge to cancel the target's active remote login
**So that** a racing successful login cannot restore authentication state after offboarding

## Acceptance Criteria

- [ ] **Given** the target has a non-terminal remote-auth attempt, **When** purge begins, **Then**
  the attempt becomes cancelled under the manager lock.
- [ ] **Given** cancellation wins before successful capture, **When** the runner later returns
  success, **Then** no cookies are persisted.
- [ ] **Given** successful capture wins before cancellation, **When** purge continues, **Then** the
  newly captured target session is deleted.
- [ ] **Given** no matching attempt exists, **When** purge runs, **Then** cancellation is a safe
  no-op.

## Technical Notes

- The target-cancel operation must use the same lock as `_run_attempt` terminal capture.
- Worker/browser-gate cleanup remains owned by the existing runner completion path.

## Dependencies

### Requires

- US-097 complete session deletion ordering.

### Enables

- Truthful complete purge under concurrent remote login.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Attempt already terminal | No state change; subsequent session deletion still runs |
| Target has no Telegram identity | Skip remote cancellation; continue local cleanup |

## Out of Scope

- Suppressing an already-delivered success notification in the capture-wins race.
