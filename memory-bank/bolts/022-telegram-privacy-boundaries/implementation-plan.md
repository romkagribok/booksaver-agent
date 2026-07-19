---
stage: plan
bolt: 022-telegram-privacy-boundaries
created: 2026-07-19T02:50:44Z
---

# Implementation Plan: Telegram Privacy Boundaries

## Objective

Make Telegram a private-chat-only, caller-scoped interface in which exact booking-derived data reaches
only its active owner, administration consumes an explicit aggregate projection, and revocation is
rechecked at every queued, waiting, completion, notification, and handoff boundary.

## Boundary Decisions

- Bot API `chat.type` is trusted update metadata; missing/unknown values fail closed before handlers.
- Owner privilege grants administration but never bypasses record ownership in ordinary commands.
- Exact-data adapters use caller-owned repositories/resolvers; foreign and missing selectors match.
- Admin usage receives only an allowlisted DTO built from SQL counts plus injected coordinator
  snapshots. Exact domain repositories never feed the formatter.
- Already-running browser work may finish/persist locally when cancellation is unsafe, but no savings
  pipeline, key/cap notice, sensitive completion, or alert follows a detected revocation.
- Rebook confirmation waits poll active-user state so revocation releases the active-session guard
  promptly rather than waiting for the full Telegram timeout.

## Deliverables

1. Private update admission
   - Fail closed on group, supergroup, channel, missing, and unknown chat types before authorization,
     invite redemption, dialogs, key validation, callbacks, browser, or LLM work.
2. Caller-only exact data
   - Replace global `/status` enumeration with daemon health plus caller aggregate count.
   - Preserve scoped selectors and mask foreign confirmation uniqueness conflicts in register/edit.
3. Aggregate owner administration
   - Add an allowlisted admin usage row and SQL `COUNT` query.
   - Inject check/LLM counter snapshots from CheckCoordinator; label UTC-midnight/restart semantics and
     report unavailable data explicitly.
4. Revocation-aware asynchronous boundaries
   - Recheck scheduled queue items before allowance/browser and notices before send.
   - Recheck immediate work before SavingsPipeline and completion disclosure.
   - Poll access during guided-rebook waits and recheck before prompts, handoff, and final replies.
5. Regression contract
   - Add a maintained privacy matrix and two-user sentinel tests across command/callback/dialog,
     admin, immediate/scheduled, rebook, and notification families.

## Verification

- Focused Telegram, persistence, coordinator, notifier, and rebook tests.
- Full pytest, Ruff, mypy, diff check, and artifact validation.
- Formal close/commit/push only after the requested combined human review.
