---
stage: test
bolt: 039-agent-assisted-booking-inventory
created: 2026-08-02T19:14:42Z
status: complete
---

# Test Report: Agent-Assisted Booking Inventory

## Outcome

Authenticated Booking.com inventory remains deterministic-first and now enters the shared guarded
recovery boundary for changed entry/readiness, scope, pagination, detail, and interpretation steps.
Assisted observations retain exact visible identity but cannot independently supply lifecycle or
other eligibility-driving facts. Only deterministic scope and terminal navigation evidence can make
a synchronization complete or mark an unseen reservation absent.

## Safety and Privacy Coverage

- Unsafe/external/checkout/payment/cancellation pages stop before verification, provider disclosure,
  screenshots, or browser actions.
- Playwright sanitizes current URLs, popup URLs, and link destinations before model observation.
- Inventory recovery rejects fill/select and permits clicks only on machine-classified read-only
  scope, pagination, and reservation-detail controls.
- Persistent tab aliases, count-only labels, scrolling, and element-ref churn cannot prove a scope
  complete; changed count-suffixed read-only scope labels remain recoverable.
- Visible unidentified cards always prevent a complete run, even when typed interpretation recovers
  positive evidence, and button-only `Load more` pagination requires named guarded recovery until a
  terminal page is proved.
- LLM inventory facts cannot create an eligible monitoring projection without deterministic facts.
- An assisted observation of an existing reservation can add missing grounded display metadata but
  cannot replace authoritative eligibility facts or archive its active monitoring projection.
- Authentication, MFA, and captcha evidence reached after an action terminates before another model
  turn, while the outer check deadline is rechecked across traversal, provider calls, and actions.
- Caller-scoped key resolution fails closed, daily calls are counted once, and personal-key errors
  retain `/setkey`/`/deletekey` guidance.
- Schema v13 stores a write-once, caller-scoped, content-free recovery audit with provider/model/
  role/prompt metadata, calls, tokens, actual actions, duration, and bounded progress events.
- `/bookings` and `/checknow` distinguish complete, incomplete, authentication, key, and unexpected
  refresh failures without rendering stale state as a fresh empty account.

## Evaluation and Operational Coverage

- Replay metrics include correctness, safety, outcomes, calls, actual actions, latency, and provider
  input/output token usage.
- Live replay requires explicit opt-in, uses no browser/database/session, caps runs at ten, rejects
  directories above 20 fixtures, and rejects plans above 250 possible provider calls.
- `booksaver bookings trace <SYNC_RUN_ID>` exposes the content-free owner-scoped inventory audit;
  price checks retain `booksaver checks trace <CHECK_ID>`.

## Verification Evidence

| Gate | Result |
|---|---:|
| Final inventory/browser/persistence release-blocker regression set | 88 passed |
| Inventory/coordinator/Telegram/audit focused integration set | 168 passed |
| Full repository test suite | 1225 passed |
| Ruff across `src` and `tests` | Passed |
| Strict mypy across 103 source files | Passed |
| CLI help, example config validation/show, booking/evaluation help | Passed with `PYTHONPATH=src` |
| AI-DLC artifact validator | Passed before final completion propagation |
| Diff whitespace validation | Passed |

The suite emitted 49 expected legacy `schedule.check_interval` deprecation warnings; no test failed.

## Story Coverage

- **US-126**: Named deterministic-first account navigation and interpretation recovery shared by
  `/bookings`, post-connect, `/checknow`, and scheduled synchronization.
- **US-127**: Deterministic completeness authority, non-eligible LLM-only evidence, read-only action
  allowlist, destination privacy, and partial-run preservation.
- **US-128**: Accurate Telegram outcomes, caller-scoped accounting, schema-v13 recovery audit, and
  local operator inspection.

## Deferred Live Acceptance

No production provider, Booking.com, Telegram, Docker, or VPS call was made. After owner review and
separate approval to merge/deploy, acceptance should run the packaged live replay and real-user
`/status`, `/bookings`, then `/checknow` smoke flow with an eligible reservation.
