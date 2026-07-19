---
stage: plan
bolt: 021-invite-first-access
created: 2026-07-19T02:39:40Z
---

# Implementation Plan: Invite-First Access

## Objective

Make private Telegram sharing consistently invite-first, give the owner recognizable but non-
authoritative username labels, deliver a clean copyable invite command, and make revocation explicit
without weakening user scoping, key isolation, quotas, or owner-only administration.

## Prior Decisions Applied

- **ADR-018**: The bot remains self-hosted and private on an owner-operated laptop or VPS.
- **ADR-019**: Personal API keys remain encrypted and isolated per user.
- **ADR-021**: Check limits and execution remain in the shared coordinator.
- **New ADR-022**: Fixed invite-first non-owner admission supersedes Bolt 009's runtime owner/invite
  mode while retaining the owner role and rejecting public access.

## Deliverables

1. Invite-first configuration and access
   - Normalize absent and legacy private access-mode values to one fixed invite-first policy.
   - Reject public/open/unknown values, remove `/admin mode`, and omit the field from generated config.
   - Keep the owner fast path and owner-only admin authorization.
2. Recognizable optional identity
   - Add schema v9 nullable `telegram_username` with an additive, idempotent migration.
   - Carry optional username on messages and callbacks, normalize without `@`, refresh/clear only
     after successful authorization, and never use it for access.
   - Render `@username` or `User #N (no @username)` in owner admin surfaces without chat IDs.
3. Copyable invite and revocation experience
   - Create exactly one invite and send guidance followed by exact `/start <code>` in a new message.
   - Commit revocation first, attempt the exact access-loss message directly, and report delivery
     outcome accurately to the owner.
   - Distinguish revoked from unknown internally so eligible commands/callbacks receive the exact
     access-loss explanation while strangers retain the generic response.
4. Regression proof and documentation
   - Cover fresh/v8 migration, message/callback username capture, legacy config, fixed admission,
     two-message invite behavior, delivery failures, revoked refusals, and owner-only admin behavior.
   - Update current config samples, operational guidance, architecture index, and story artifacts.

## Planned Source Changes

- `domain/user.py`, `persistence/schema.sql`, `persistence/sqlite_store.py`: schema-v9 username model
  and repository operations.
- `telegram/router.py`, `bot_loop.py`, `access.py`, `gateway.py`: trusted username propagation and
  fixed invite-first decisions with state-aware refusal.
- `telegram/admin_commands.py`: username labels, aggregate-safe selector preparation, separate invite
  message, direct revoke notice, and removal of mode controls.
- `domain/value_objects.py`, `application/load_config.py`, config templates/runbook: legacy input
  normalization and current invite-first documentation.
- `memory-bank/bolts/021-invite-first-access/adr-022-fixed-invite-first-admission.md` and decision index.

## Verification

- Focused persistence, access-control, bot-loop, gateway, admin-command, and config tests.
- Full `pytest`, Ruff, mypy, `git diff --check`, and artifact validation.
- No closure, commit, or push until the product owner's final implementation review.
