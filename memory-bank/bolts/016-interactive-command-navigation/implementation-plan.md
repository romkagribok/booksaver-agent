---
stage: plan
bolt: 016-interactive-command-navigation
created: 2026-07-18T22:14:33Z
---

## Implementation Plan: Interactive Command Navigation

### Objective

Make current Telegram commands and their enumerable inputs selectable while preserving every existing
authorization, ownership, confirmation, and typed-command contract.

### Deliverables

- Authoritative command catalog used by `/help` and `setMyCommands`.
- Telegram client support for scoped command publication with nonfatal gateway synchronization.
- Reusable callback router with duplicate rejection and unknown/stale acknowledgement.
- Callback access guard before dispatch.
- `/checks` booking keyboard and `/rebook` savings-opportunity keyboard.
- `/admin` action, target, mode, confirmation, cancel, and back keyboards.
- Compatibility/security tests at client, router, command, admin, rebook, bot-loop, and gateway levels.

### Dependencies

- Existing TelegramBotClient HTTPS seam and test transport.
- Existing BotLoop callback parsing and AccessControl.
- Existing user-scoped booking/savings/user repositories.
- Existing rebook PendingPromptRegistry and session guard.

### Technical Approach

Add a prefix-based `CallbackRouter` beside `CommandRouter`. Gateway wiring registers each feature
family and supplies one guarded dispatcher to `BotLoop`. Command handlers render inline keyboards only
when a typed argument is absent, encode bounded authoritative IDs, and re-run the same scoped operation
after selection. Admin callbacks recheck owner status and reload target users immediately before a
confirmed action. A static command catalog generates help and Telegram command definitions; startup
publication failures are logged and ignored.

### Acceptance Criteria

- [x] Default and owner-scoped command definitions are synchronized at startup.
- [x] Command publication failure cannot prevent long polling.
- [x] Every callback is authorized, routed once, and acknowledged.
- [x] Unknown/stale callbacks get a neutral expired response.
- [x] Checks/rebook keyboards contain only caller-owned data and use recognizable labels.
- [x] Forged or cross-user selections perform no protected action.
- [x] Admin menus disclose/act only for owner and confirm every UI mutation.
- [x] Typed commands and existing rebook callbacks remain supported.
- [x] No dependency/schema/architecture expansion is introduced.
- [x] Focused/full automated and static gates pass.

### Process Authorization

The product owner explicitly authorized autonomous AI-DLC progression through Plan, Implement, and
Test with one compressed validation immediately before official bolt completion.
