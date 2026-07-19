---
id: 002-scope-status-and-selectors
unit: 001-telegram-privacy-boundaries
intent: 010-telegram-privacy-boundaries
status: complete
priority: must
created: 2026-07-19T02:34:19Z
assigned_bolt: 022-telegram-privacy-boundaries
implemented: true
---

# Story: Scope Status and Selectors

**Global story ID**: US-068

## User Story

**As an** active BookSaver user
**I want** every status, picker, typed selector, and callback to operate inside my ownership scope
**So that** neither ordinary users nor the owner can inspect another user's exact records in Telegram

## Acceptance Criteria

- [ ] `/status` shows safe daemon health and caller aggregates without enumerating exact records.
- [ ] Booking, savings, checks, check-now, edit/delete, and rebook selectors return caller-owned data only.
- [ ] Foreign, unknown, stale, short, and ambiguous typed/callback identifiers share a non-enumerating response.
- [ ] Crafted foreign selectors perform no mutation, browser/LLM work, or sensitive completion.
- [ ] Registration/edit confirmation conflicts preserve global uniqueness without revealing foreign existence.
- [ ] Owner ordinary commands are scoped to owner-owned records exactly like invited users.

## Technical Notes

- Replace raw unscoped reads in Telegram formatters with a caller-scoped query/application boundary.
- Preserve immutable identifiers internally; do not make username an authorization key.
- For confirmation conflicts, distinguish own duplicate only inside the service; mask foreign conflict.

## Dependencies

### Requires

- US-067 private-chat admission.
- Bolts 017 and 019 selector/callback families.

### Enables

- US-069 aggregate-only administration.
- US-071 cross-user selector matrix.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Owner invokes `/status` with invited users present | No invited-user property, ID, outcome, or count |
| User crafts another user's `checks:` callback | Same result as a stale/missing callback |
| User enters another user's confirmation during registration | Generic conflict with no existence confirmation |
| Displayed UUID prefix collides within caller scope | Generic absence; no arbitrary match |

## Out of Scope

- Changing the exact information users see for records they own via dedicated commands.
- Removing unscoped repositories required by local CLI/scheduler internals.
