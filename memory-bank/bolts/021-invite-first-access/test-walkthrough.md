---
stage: test
bolt: 021-invite-first-access
created: 2026-07-19T02:50:44Z
---

# Test Walkthrough: Invite-First Access

## Automated Results

- Focused combined suite: **124 passed** across schema migration, user scoping, access control,
  admin commands, BotLoop envelopes, gateway integration, and Telegram config.
- Full suite: **741 passed** in 5.62 seconds.
- Ruff: clean.
- mypy: clean across 77 source files.
- `git diff --check`: clean at the stage checkpoint.

## Acceptance Evidence

- Fresh v9, v8 migration, partially applied migration, username normalization/no-op/clear, and purge
  behavior are deterministic integration tests.
- Both typed and callback invite paths prove one stored code and an exact separate redemption command;
  failure proves persistence survives without logging the code or issuing another.
- Fixed invite access tests prove legacy owner config no longer disables invite redemption and public
  values remain invalid.
- Admin tests prove username/fallback labels omit Telegram IDs and mode controls are absent.
- Revocation tests prove commit-before-delivery, exact target text, delivery outcome reporting, and
  state-aware command/callback refusal.

## Formal Closure

The product owner approved the combined Bolt 021 + Bolt 022 result. A final full run passed 763 tests,
Ruff, mypy, and diff checks before the completion cascade closed the bolt.
