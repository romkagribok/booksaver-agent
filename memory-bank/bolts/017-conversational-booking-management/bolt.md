---
id: 017-conversational-booking-management
unit: 001-conversational-booking-management
intent: 006-telegram-booking-management
type: simple-construction-bolt
status: complete
stories:
  - 001-discover-booking-management-commands
  - 002-edit-owned-booking-selectively
  - 003-delete-owned-booking-after-confirmation
  - 004-preserve-booking-mutation-integrity
created: 2026-07-18T22:40:07.000Z
started: 2026-07-18T22:40:07.000Z
completed: "2026-07-18T23:19:09Z"
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-18T22:40:07.000Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-18T22:58:23.000Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-18T22:59:43.000Z
    artifact: test-walkthrough.md
requires_bolts:
  - 016-interactive-command-navigation
  - 018-interactive-command-navigation
enables_bolts: []
requires_units:
  - 001-interactive-command-navigation
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: 017-conversational-booking-management

## Objective

Deliver caller-scoped, discoverable Telegram edit and confirmed-delete booking flows plus explicit
repository mutations that preserve aggregate and relational integrity.

## Stories Included

- [ ] **US-048**: Discover booking management commands - implemented, awaiting closure.
- [ ] **US-049**: Edit an owned booking selectively - implemented, awaiting closure.
- [ ] **US-050**: Delete an owned booking after confirmation - implemented, awaiting closure.
- [ ] **US-051**: Preserve booking mutation integrity - implemented, awaiting closure.

## Expected Outputs

- Command-catalog and gateway wiring for `/editbooking` and `/deletebooking`.
- Interactive booking/field/confirmation callbacks and validated edit dialogs.
- Whole-booking update and transactional cascade-delete repository operations.
- Focused Telegram/persistence tests plus full quality verification.
- Simple-bolt Plan, Implement, and Test walkthrough artifacts.

## Dependencies

- **016-interactive-command-navigation**: Completed command catalog and callback router.
- Existing schema v8 booking/user relationships and registration validators.

## Success Criteria

- [x] Every enumerable choice is a button and every mutation is caller scoped.
- [x] Delete cannot execute without a distinct Confirm callback.
- [x] Edit preserves identity/history safety and delete leaves no booking-scoped orphan data.
- [x] Typed shortcuts remain usable and all quality gates pass.

## Execution Note

Intermediate checkpoints were covered by the product owner's continuous-flow authorization. The
product owner approved the final Test checkpoint and documented mutation decisions; post-hotfix
integration verification passed on 2026-07-18T23:18:36Z. The official completion script closed the
bolt on 2026-07-18T23:19:09Z.
