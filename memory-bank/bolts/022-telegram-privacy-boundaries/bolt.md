---
id: 022-telegram-privacy-boundaries
unit: 001-telegram-privacy-boundaries
intent: 010-telegram-privacy-boundaries
type: simple-construction-bolt
status: complete
stories:
  - 001-restrict-interaction-to-private-chats
  - 002-scope-status-and-selectors
  - 003-show-aggregate-admin-usage
  - 004-stop-work-after-revocation
  - 005-prove-cross-user-isolation
created: 2026-07-19T02:34:19Z
started: 2026-07-19T02:50:44Z
completed: 2026-07-19T14:48:51Z
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-19T02:50:44Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-19T03:05:03Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-19T03:05:03Z
    artifact: test-walkthrough.md
requires_bolts:
  - 021-invite-first-access
  - 017-conversational-booking-management
  - 019-on-demand-check-orchestration
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 022-telegram-privacy-boundaries

## Overview

One cohesive privacy-hardening bolt for Telegram update admission, exact-data scoping, aggregate admin
usage, revocation-aware asynchronous execution/delivery, and adversarial multi-user proof.

## Objective

Ensure every Telegram surface is private-chat-only and least-privileged: exact data reaches only its
active owner, administration receives aggregate usage only, and revocation is honored before queued
cost and later sensitive messaging.

## Stories Included

- **001-restrict-interaction-to-private-chats / US-067**: Private-chat-only admission (Must)
- **002-scope-status-and-selectors / US-068**: Caller-scoped exact data (Must)
- **003-show-aggregate-admin-usage / US-069**: Aggregate-only admin projection (Must)
- **004-stop-work-after-revocation / US-070**: Async revocation rechecks (Must)
- **005-prove-cross-user-isolation / US-071**: Adversarial privacy matrix (Must)

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

## Stages

- ✅ **1. plan**: Complete → `implementation-plan.md`
- ✅ **2. implement**: Complete → `implementation-walkthrough.md`
- ✅ **3. test**: Complete → `test-walkthrough.md`

## Dependencies

### Requires

- `021-invite-first-access` — complete and green.
- `017-conversational-booking-management` — complete; supplies edit/delete surfaces.
- `019-on-demand-check-orchestration` — complete; supplies immediate/scheduled coordinator seams.

### Enables

- Privacy-safe expansion of the invite-only Telegram bot.

## Success Criteria

- [x] All five stories implemented and acceptance criteria satisfied.
- [x] Non-private chats reach no sensitive, mutating, or expensive handler.
- [x] Two-user sentinels prove zero cross-user disclosure or mutation.
- [x] Admin formatting consumes only the allowlisted aggregate projection.
- [x] Revocation timing tests suppress queued work and later sensitive delivery.
- [x] Ruff, mypy, full pytest, diff, and AI-DLC validation pass with no new validator issues.
- [x] Human final review approved closure before commit and push.

## Notes

The product owner approved the combined review. Bolts 021 and 022 were closed in dependency order
after the final 763-test verification.
