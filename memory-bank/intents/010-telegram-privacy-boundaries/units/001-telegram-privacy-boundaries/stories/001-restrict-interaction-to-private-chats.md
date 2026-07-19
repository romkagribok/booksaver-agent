---
id: 001-restrict-interaction-to-private-chats
unit: 001-telegram-privacy-boundaries
intent: 010-telegram-privacy-boundaries
status: complete
priority: must
created: 2026-07-19T02:34:19Z
assigned_bolt: 022-telegram-privacy-boundaries
implemented: true
---

# Story: Restrict Interaction to Private Chats

**Global story ID**: US-067

## User Story

**As an** admitted BookSaver user
**I want** all bot interactions containing personal booking data to remain in my private chat
**So that** my records, dialogs, and API-key material are not exposed to a Telegram group

## Acceptance Criteria

- [ ] Message and callback envelopes carry Telegram's server-provided chat type into authorization.
- [ ] Missing or unknown chat types fail closed as non-private.
- [ ] Group, supergroup, and channel commands/callbacks are generically refused before routing.
- [ ] Plain dialog replies and key material from non-private chats never reach dialog/key handlers.
- [ ] Refused non-private updates trigger no database mutation, key validation, browser, or LLM work.
- [ ] An active sender ID cannot override chat-type denial; private admitted behavior is unchanged.

## Technical Notes

- Preserve immutable inbound envelopes and derive chat type only from Bot API metadata.
- Enforce once at the earliest gateway/access boundary, with callbacks covered equally.
- Do not depend solely on Telegram command-menu scopes or bot privacy mode.

## Dependencies

### Requires

- Intent 003 Telegram gateway and access control.
- Intent 009 invite-only sharing configuration.

### Enables

- US-068 caller-scoped exact-data behavior.
- US-071 non-private-chat regression matrix.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Active user invokes `/bookings` in a group | Generic refusal; no booking text |
| Group sends a crafted inline callback | Callback is acknowledged/refused; handler is not called |
| User began a private dialog, then replies in a group | Group reply cannot advance private state |
| API key is pasted into a group | No validation/storage; no echo or detailed response |

## Out of Scope

- Preventing users from manually forwarding their own private bot messages.
- Telegram Secret Chats, which bots do not participate in.
