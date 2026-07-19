---
stage: implement
bolt: 021-invite-first-access
created: 2026-07-19T02:50:44Z
---

# Implementation Walkthrough: Invite-First Access

## Summary

Implemented one fixed invite-first Telegram access posture with copyable invite handoff, optional
owner-visible username labels, explicit revocation, and migration-safe compatibility for deployed VPS
configurations. Stable Telegram numeric IDs remain authoritative and no public mode was introduced.

## Delivered Changes

- Schema v9 and identity
  - Added nullable, non-unique `users.telegram_username` and guarded v8→v9 migration.
  - Added normalized, change-aware username persistence including explicit clearing.
  - Propagated optional message/callback usernames from Telegram metadata into successful access.
  - Prevented unknown, invalid-invite, and revoked traffic from mutating identity metadata.
- Fixed invite-first policy
  - Removed runtime access-mode state, mutator, command, and inline menu.
  - Active known users and one-time invite redemption are the only non-owner admissions.
  - Legacy absent/`owner`/`invite` config normalizes to invite; public/unknown values remain invalid.
  - Added ADR-022 and current documentation/config guidance.
- Owner administration
  - Admin identity labels prefer `@username`; fallback uses internal user number without Telegram ID.
  - Invite creation emits guidance then exact `/start <code>` in a distinct new message.
  - Revoke commits first, directly attempts the exact access-loss notice, and accurately reports
    delivered/failed/unavailable to the owner.
- Refusal behavior
  - Revoked commands receive the exact access-loss message subject to the refusal window.
  - Every revoked callback is acknowledged with the exact message.
  - Unknown users and unusable invites retain generic responses.

## Safety Preservation

- Invite codes remain single-use bearer secrets and are absent from failure logs.
- Personal-key encryption, owner billing fallback, check budgets, record ownership, alerts, and
  rebook confirmation paths were not changed.
- The direct revoke notice bypasses only the generic reply limiter; Telegram errors cannot roll back
  persisted revocation.

## Review State

The product owner approved the combined Bolt 021 + Bolt 022 review, and the mandatory completion
cascade closed this bolt after final verification.
