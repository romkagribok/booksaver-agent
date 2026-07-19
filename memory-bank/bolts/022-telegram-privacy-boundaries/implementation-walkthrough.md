---
stage: implement
bolt: 022-telegram-privacy-boundaries
created: 2026-07-19T03:05:03Z
---

# Implementation Walkthrough: Telegram Privacy Boundaries

## Summary

Implemented a fail-closed Telegram privacy boundary across inbound updates, caller exact-data queries,
owner administration, queued checks, notifications, and guided-rebook workers. The guarantee isolates
bot users through Telegram; it does not claim secrecy from the self-hosted machine operator or the
external processors already required by BookSaver.

## Delivered Changes

- Private-chat admission
  - BotLoop marks missing chat type `unknown`; the gateway rejects every non-`private` message and
    callback before access lookup, invite redemption, dialog/key handling, mutation, browser, or LLM.
  - Group callbacks are acknowledged generically without dispatch.
- Caller-only exact data
  - `/status` now shows daemon health/session plus only `Your active bookings: N`.
  - Existing booking/check/savings/check-now/edit/delete/rebook selectors remain caller-scoped.
  - Foreign confirmation conflicts during register/edit are masked while own duplicates may be
    explained safely.
- Aggregate-only administration
  - Added an allowlisted `AdminUserAggregate` SQL projection with active-booking `COUNT`.
  - Added typed coordinator usage snapshots for checks and actual LLM calls; unavailable runtime
    counters are explicit and never fabricated.
  - Removed chat IDs, key state, and all exact booking/check/savings/rebook data from admin output and
    avoided loading exact records for user listings/pickers.
- Revocation barriers
  - Scheduled browser startup is lazy and follows current active-user/allowance checks.
  - Mid-flight local check history may persist, but SavingsPipeline, key notices, completion details,
    and alerts are suppressed after revocation.
  - Cap/key notices and owner/invited savings routing require a currently active user.
  - Rebook waits poll access at most every second and reauthorize before prompt edits, handoffs,
    outcome questions, errors, and final replies; the session guard always releases.
- Regression contract
  - Added `privacy-matrix.md` and adversarial tests across non-private updates, status, confirmation
    oracles, admin aggregates, foreign selectors, scheduled/immediate work, notices, and rebook waits.

## Known Physical Limit

Like any networked authorization check, there is an irreducible tiny race between the final active
read and the immediately adjacent Telegram send. Every controllable queue, wait, processing, and send
boundary is rechecked, and deterministic tests cover the practical revocation windows.

## Review State

The product owner approved the combined Bolt 021 + Bolt 022 review, and the mandatory completion
cascade closed this bolt after final verification.
