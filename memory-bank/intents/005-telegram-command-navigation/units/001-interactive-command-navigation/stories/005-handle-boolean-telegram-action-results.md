---
id: 005-handle-boolean-telegram-action-results
unit: 001-interactive-command-navigation
intent: 005-telegram-command-navigation
status: complete
priority: must
created: 2026-07-18T22:57:59.000Z
assigned_bolt: 018-interactive-command-navigation
implemented: true
---

# Story: Handle Boolean Telegram Action Results

**Global story ID**: US-047

## User Story

**As an** authorized Telegram user
**I want** a booking button tap to render its result reliably
**So that** an acknowledged callback never disappears without visible feedback

## Acceptance Criteria

- [ ] **Given** Telegram returns Boolean `true` for `answerCallbackQuery`, **When** the client handles
  the response, **Then** it returns success without attempting object conversion.
- [ ] **Given** Telegram returns Boolean `true` for `deleteMessage`, **When** the client handles the
  response, **Then** it returns success without attempting object conversion.
- [ ] **Given** a `/checks` booking button is tapped, **When** acknowledgement succeeds or fails,
  **Then** the handler still attempts to render the scoped check-history result.
- [ ] **Given** acknowledgement or message editing fails, **When** a callback is handled, **Then** the
  failure is logged rather than silently discarded and no bot-loop crash occurs.
- [ ] **Given** a `/rebook` opportunity button is tapped, **When** acknowledgement or picker-message
  editing fails, **Then** the existing ownership-checked guided operation still receives the selection.

## Technical Notes

- Telegram's Bot API returns a JSON Boolean from action methods such as `answerCallbackQuery` and
  `deleteMessage`; object-returning methods such as `sendMessage` and `editMessageText` remain maps.
- Keep acknowledgement, rendering, and protected action invocation as independent failure domains.

## Dependencies

### Requires

- US-044 callback routing and US-045 booking/opportunity selection.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Callback acknowledgement succeeds but edit fails | Spinner stops; edit failure is logged |
| Callback acknowledgement fails but edit succeeds | Result still appears; acknowledgement failure is logged |
| Picker message was deleted before edit | Protected action remains scoped and proceeds only if valid |

## Out of Scope

- Retrying Telegram writes or persisting outbound messages.
