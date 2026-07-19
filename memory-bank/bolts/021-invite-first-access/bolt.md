---
id: 021-invite-first-access
unit: 001-invite-first-access
intent: 009-invite-first-sharing
type: simple-construction-bolt
status: complete
stories:
  - 001-deliver-copyable-invite-command
  - 002-maintain-recognizable-usernames
  - 003-enforce-invite-only-admission
  - 004-explain-revoked-access
  - 005-preserve-sharing-safety
created: 2026-07-19T02:34:21Z
started: 2026-07-19T02:39:40Z
completed: 2026-07-19T14:48:51Z
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-19T02:39:40Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-19T02:50:44Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-19T02:50:44Z
    artifact: test-walkthrough.md
requires_bolts:
  - 009-user-access-and-keys
  - 016-interactive-command-navigation
enables_bolts:
  - 022-telegram-privacy-boundaries
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 021-invite-first-access

## Overview

Refine the existing Telegram access and administration surface into one fixed invite-first sharing
experience with copyable handoff, owner-recognizable identity metadata, and explicit revocation.

## Objective

Deliver all five Invite-First Sharing stories as one cohesive change while preserving stable-ID
authorization, private admission, user scoping, encrypted keys, budgets, and owner-only administration.

## Stories Included

- [x] **001-deliver-copyable-invite-command / US-062**: Send the exact invite command separately (Must).
- [x] **002-maintain-recognizable-usernames / US-063**: Persist and owner-display current usernames (Must).
- [x] **003-enforce-invite-only-admission / US-064**: Remove owner-only admission mode (Must).
- [x] **004-explain-revoked-access / US-065**: Notify and later explain revoked access (Must).
- [x] **005-preserve-sharing-safety / US-066**: Prove existing trust boundaries remain intact (Must).

## Bolt Type

**Type**: Simple Construction Bolt.
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`.

## Stages

- [x] **1. Plan**: Complete → `implementation-plan.md`.
- [x] **2. Implement**: Complete → source changes + `implementation-walkthrough.md`.
- [x] **3. Test**: Complete → tests + `test-walkthrough.md`.

## Dependencies

### Requires

- `009-user-access-and-keys`: Users, access states, invite codes, encrypted keys, and owner admin commands.
- `016-interactive-command-navigation`: Guarded callback routing and inline owner administration.

### Enables

- A stable invite-first sharing workflow ready for owner-led Telegram testing.
- Intent 010 privacy work to refine owner-visible usage without revisiting admission mechanics.

## Expected Outputs

- Two-message invite command delivery for typed and callback administration.
- Schema v9 optional username metadata, migration, propagation, owner labels, and purge behavior.
- Fixed invite-first access control and compatible legacy private-config handling.
- State-aware command/callback refusal plus best-effort proactive revoke notification.
- New ADR, updated current documentation/config examples, focused/full verification, and walkthroughs.

## Success Criteria

- [x] All five stories and acceptance criteria are implemented.
- [x] Stable numeric Telegram ID remains the sole authorization key.
- [x] Unknown users cannot distinguish invite or account state.
- [x] Durable invite/revoke state survives Telegram delivery failure.
- [x] Existing user-data, key, budget, and rebook boundaries remain unchanged.
- [x] Focused/full pytest, Ruff, mypy, and AI-DLC consistency checks pass with no new validator issues.

## Notes

The product owner approved the combined implementation review. The mandatory completion cascade ran
after the final 763-test verification.
