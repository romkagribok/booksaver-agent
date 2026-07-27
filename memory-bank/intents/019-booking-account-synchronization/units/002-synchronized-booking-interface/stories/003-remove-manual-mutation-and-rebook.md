---
id: 003-remove-manual-mutation-and-rebook
unit: 002-synchronized-booking-interface
intent: 019-booking-account-synchronization
status: complete
priority: must
created: 2026-07-27T16:28:04.000Z
assigned_bolt: 036-synchronized-booking-interface
implemented: true
---

# Story: US-118 Remove manual booking mutation and guided rebooking

## User Story

**As the** BookSaver product owner
**I want** obsolete mutation and rebooking behavior removed immediately
**So that** the product has one clear read-only source of reservation truth.

## Acceptance Criteria

- [ ] `/register`, `/editbooking`, `/deletebooking`, and `/rebook` are absent from command
  publication, help, handlers, callbacks, dialogs, tests, and normal documentation.
- [ ] Typed retired commands are immediately unknown and have no compatibility alias.
- [ ] Normal CLI booking mutation and operator legacy-migration paths are removed.
- [ ] Savings notification and `/savings` remain informational without creating rebook sessions.
- [ ] Existing generic dialog cancellation remains only for unrelated surviving flows.
- [ ] No code path can manually change synchronized reservation facts or infer/execute rebooking.

## Dependencies

### Requires
- Unit 001 complete.

### Enables
- Final release verification.

## Out of Scope

- Removal of unrelated access, key, check, savings, or admin commands.
