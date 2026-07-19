---
id: 005-preserve-sharing-safety
unit: 001-invite-first-access
intent: 009-invite-first-sharing
status: complete
priority: must
created: 2026-07-19T02:34:21Z
assigned_bolt: 021-invite-first-access
implemented: true
---

# Story: Preserve Sharing Safety

**Global story ID**: US-066

## User Story

**As a** BookSaver owner or invited user
**I want** sharing improvements to preserve existing trust boundaries
**So that** recognizable access does not expose data, secrets, or spending authority

## Acceptance Criteria

- [ ] `/admin`, invite creation, user listing, revoke, and purge remain owner-only for commands and callbacks.
- [ ] Invite codes remain unguessable, single-use, and absent from logs.
- [ ] Usernames appear only in owner administration and never in user-facing lists, traces, or logs.
- [ ] Purge removes username metadata; revoke retains it under the existing retained-data policy.
- [ ] Booking/check/savings scoping, daily limits, owner-billed fallback, encrypted personal keys, and
  rebook confirmation remain unchanged.
- [ ] Focused migration/access/gateway/admin tests and full pytest, Ruff, mypy, and AI-DLC checks pass.

## Technical Notes

- Prefer regression assertions at existing repository, gateway, notification, and command seams.
- Do not create a second access path, Telegram client, or user identity source.

## Dependencies

### Requires

- US-062 through US-065.
- Completed user scoping, key isolation, limits, and guided-rebook foundations.

### Enables

- Safe deployment and owner-led sharing validation on the VPS.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Invited user sends `/admin` or admin callback data | Refused before any admin data or mutation is exposed |
| Username contains unusual but valid characters | Displayed as plain owner-only text; never interpreted as identity |
| User is purged after using an invite | User row and username disappear with existing cascade cleanup |

## Out of Scope

- Broad user-data privacy redesign or owner usage aggregation; covered by Intent 010.
- Changes to quota values, encryption algorithms, or rebook safety rules.
