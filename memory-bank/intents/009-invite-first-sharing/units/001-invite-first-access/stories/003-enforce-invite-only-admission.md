---
id: 003-enforce-invite-only-admission
unit: 001-invite-first-access
intent: 009-invite-first-sharing
status: complete
priority: must
created: 2026-07-19T02:34:21Z
assigned_bolt: 021-invite-first-access
implemented: true
---

# Story: Enforce Invite-Only Non-Owner Admission

**Global story ID**: US-064

## User Story

**As a** BookSaver owner
**I want** every non-owner admitted only through an explicit invite
**So that** sharing is consistently private without a confusing runtime access mode

## Acceptance Criteria

- [ ] The owner remains always authorized and remains the sole administrator.
- [ ] An active known user is authorized and a stranger requires one valid unused invite.
- [ ] A code admits at most one user and known active users remain admitted after restart.
- [ ] `/admin mode`, its inline menu, and the runtime mode mutator are removed.
- [ ] Production authorization has no owner-versus-invite mode branch.
- [ ] Missing, legacy `access_mode = "owner"`, and `"invite"` all normalize to fixed invite-first
  posture; `"open"`, `"public"`, and unknown values remain invalid.
- [ ] Newly generated config omits the legacy access-mode setting.
- [ ] Generated configuration and documentation describe a private invite-only bot.

## Technical Notes

- Preserve legacy private values as ignored compatibility input or equivalent deprecation handling.
- Record the fixed-policy change in a new ADR that supersedes, rather than rewrites, Bolt 009 history.

## Dependencies

### Requires

- US-062 copyable invite command.
- Bolt 009 stable-ID access control and single-use invite semantics.

### Enables

- One predictable sharing posture for US-065 and US-066.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Deployed config still says `owner` | Daemon starts and valid invites work |
| Deployed config says `invite` | Daemon starts with unchanged invite-first behavior |
| Config says `open` or `public` | Validation still rejects it |
| Used or expired code is presented | Generic refusal identical to no valid code |

## Out of Scope

- Removing the owner role or opening administration to invited users.
- Public/open admission or reusable invitations.
