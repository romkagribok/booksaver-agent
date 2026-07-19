---
id: 005-prove-cross-user-isolation
unit: 001-telegram-privacy-boundaries
intent: 010-telegram-privacy-boundaries
status: complete
priority: must
created: 2026-07-19T02:34:19Z
assigned_bolt: 022-telegram-privacy-boundaries
implemented: true
---

# Story: Prove Cross-User Isolation

**Global story ID**: US-071

## User Story

**As an** operator inviting multiple users
**I want** one adversarial regression contract across every Telegram surface
**So that** future features cannot silently reintroduce cross-user disclosure or mutation

## Acceptance Criteria

- [ ] A maintained privacy matrix maps every command, callback/dialog, completion, and notification to
  data class, authorization seam, and denial behavior.
- [ ] Two users receive distinct sentinel properties, confirmations, record IDs, prices, outcomes,
  failure details, and savings; no response contains the other user's sentinel.
- [ ] Crafted callbacks cover `checks:`, `checknow:`, `bedit:`, `bdel:`, and `rebook:select:`.
- [ ] Typed paths cover status and all exact commands plus register/edit confirmation conflicts.
- [ ] Non-private message/callback/dialog/key tests prove zero mutation, validation, browser, or LLM work.
- [ ] Deterministic revocation barriers cover scheduled, immediate, rebook, cap/key, and savings seams.
- [ ] Admin tests fail if exact-record repositories are invoked; only aggregate SQL and injected
  in-memory counter snapshots may feed admin formatting.
- [ ] Existing own-user flows plus Ruff, mypy, full pytest, diff, and AI-DLC validation pass.

## Technical Notes

- Prefer shared sentinel fixtures/helpers so adding a Telegram command requires extending one matrix.
- Assert both absence of foreign data and absence of side effects/admissions.
- Use synchronization events instead of timing sleeps for revocation races.

## Dependencies

### Requires

- US-067 private-chat admission.
- US-068 caller-scoped selectors.
- US-069 aggregate-only admin usage.
- US-070 asynchronous revocation boundaries.

### Enables

- Safe expansion of the invite-only bot to additional trusted users.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Foreign ID exists but has no history | Same denial as entirely unknown ID |
| Callback is stale after deletion/revocation | Generic expired/unavailable response |
| Admin user has own exact records | Ordinary commands show own; admin projection stays aggregate |
| One response contains a generic currency/status word used by both users | Test uses unique sentinels to avoid false positives |

## Out of Scope

- Live multi-account Telegram end-to-end tests in CI.
- Proving secrecy from the root/operator of the self-hosted VPS.
