---
id: 001-deliver-copyable-invite-command
unit: 001-invite-first-access
intent: 009-invite-first-sharing
status: complete
priority: must
created: 2026-07-19T02:34:21Z
assigned_bolt: 021-invite-first-access
implemented: true
---

# Story: Deliver a Copyable Invite Command

**Global story ID**: US-062

## User Story

**As a** BookSaver owner
**I want** the exact invite redemption command in its own Telegram message
**So that** I can copy or forward it without editing surrounding instructions

## Acceptance Criteria

- [ ] Typed `/admin invite` creates one persisted single-use code and sends two messages.
- [ ] Inline **Create invite** acknowledges/edits the menu, creates one code, and sends a new message.
- [ ] The guidance message contains no bearer code and explains that the next message is shareable.
- [ ] The second message is exactly `/start <code>` with no extra text or decoration.
- [ ] The command contains the persisted code and remains redeemable exactly once.
- [ ] Failure to deliver the second message does not delete or mutate the persisted invite.
- [ ] A failed second send is logged without the code and creates no implicit retry, duplicate
  message, or second invite code.

## Technical Notes

- Reuse the gateway's existing rate-limited send seam for the second message; a dropped/failed send
  leaves exactly one unused code and requires an explicit owner retry.
- Callback handling must edit the existing admin message only for guidance, never for the command.
- Never log the command body or invite code.

## Dependencies

### Requires

- Bolt 009 invite-code repository and owner-only admin command.
- Bolt 016 admin callback menu and message-edit seam.

### Enables

- US-064 invite-first redemption UX.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Inline callback is replayed | Each accepted callback invocation issues at most its own one code |
| Telegram second send fails | Invite remains persisted and failure is logged without its code |
| No interactive send seam in an isolated test | Fallback responder still produces two distinct replies |

## Out of Scope

- Reusable invite links or public bot discovery.
- Automatically messaging a third party selected from the owner's contacts.
