---
stage: model
bolt: 060-agentic-inventory-executor
created: 2026-08-30T18:02:59Z
---

# Static Model: Browser Use `/bookings` Inventory Executor

## Entities

- **Bookings inventory execution**: One authorized `/bookings` refresh bound to a user, account,
  transient session lease, absolute deadline, action allowance, and cost allowance. It terminates
  after one Browser Use episode and cannot cascade to another executor.
- **Transient browser**: A fresh local Chromium process with the configured mobile identity and
  decrypted session material. It exists only for one execution and is destroyed on every terminal.
- **Browser Use episode**: A bounded sequence of model turns and at most one guarded browser action
  per step. It can submit untrusted positive observations or a closed terminal, never domain state.
- **Inventory observation**: Existing typed positive reservation and scope evidence returned through
  the provider-neutral inventory port for independent BookSaver validation.

## Value Objects

- **Inventory trigger**: Closed synchronization cause. Only `bookings` selects this adapter.
- **Guarded read-only action**: Click, scroll, safe key, or wait proposal with inspected current and
  target evidence; it contains no credentials, arbitrary URL, script, selector authority, or domain
  conclusion.
- **Destination disposition**: Closed `deny`, `observe_only`, or `interact` classification that
  separates page visibility from action authority.
- **Dialog disposition**: Code-owned decision that dismisses every prompt and confirmation dialog;
  model or harness defaults cannot accept an authenticated account mutation.
- **Execution limits**: Residual action count, computer-action count, model-cost amount, and absolute
  deadline inherited from the containing coordinator job.
- **Content-free terminal**: Closed signed-out, challenge, unavailable, unsafe, provider-failure,
  budget, action-limit, or timeout result without page/session content.

## Aggregates

- **Bookings execution aggregate**: Rooted at the execution ID. It owns the lease, transient browser,
  agent episode, model-call accounting, action accounting, and teardown. Any unsafe action, dialog,
  destination, popup, deadline, or budget outcome closes the aggregate.
- **Positive inventory evidence aggregate**: Contains only current-run positive observations and
  traversal metadata. Completeness never grants absence or deletion authority.

## Domain Events

- **Browser Use selected**: The authorized trigger is exactly `/bookings` and the capability route
  permits agentic inventory.
- **Model call reconciled**: One admitted inference is reconciled with actual provider usage before
  another physical call may begin.
- **Read-only action executed**: One inspected action passed the guard and its resulting destination
  remained observable and non-mutating.
- **Unsafe interaction rejected**: A prohibited tool, label, destination, popup, dialog, or
  post-action state terminated the execution.
- **Positive inventory submitted**: Untrusted typed evidence crossed the existing executor port.
- **Transient browser destroyed**: Browser, profile, screenshots, history, traces, and session bytes
  are unavailable after the terminal.

## Domain Services

- **Trigger-specific executor selector**: Chooses Browser Use only for `bookings` and the existing
  Stagehand executor for post-connect, `/checknow`, and scheduled synchronization.
- **Browser Use action guard**: Denies unsafe capabilities and mutation intent using inspected
  browser evidence, confines interaction to Booking.com, and re-evaluates the destination after
  execution without exact read-only labels or paths.
- **Dialog guard**: Replaces harness popup defaults and always dismisses confirm/prompt dialogs.
- **Inventory observation validator**: Existing BookSaver service that validates identities and
  facts, derives eligibility, and preserves positive-only reconciliation authority.
- **Execution budget service**: Admits and reconciles every physical model call and action against
  the containing job's hard limits.

## Repository Interfaces

- No new repository is required. Existing session, inventory, cost-ledger, and redacted execution
  metric repositories remain authoritative.

## Ubiquitous Language

- **Established agent**: Browser Use's maintained non-beta agent API, pinned exactly for reproducible
  self-hosting.
- **Generic read-only guard**: Deny-oriented interaction policy that does not encode Booking.com's
  current benign labels, selector structure, or read-only route names.
- **No same-job fallback**: A Browser Use terminal closes `/bookings`; it does not spend a second
  allowance or hide qualification failure by invoking Stagehand or legacy parsing.
- **Harness output is evidence**: Browser Use observations and terminals are untrusted inputs to
  BookSaver, never authorization, reconciliation, or transaction decisions.
