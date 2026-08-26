---
id: ADR-039
title: Capability-specific positive-only agentic inventory
status: accepted
created: 2026-08-26T03:47:00Z
bolt: 053-agentic-inventory-executor
---

# ADR-039: Capability-Specific Positive-Only Agentic Inventory

## Context

The selector-dependent Booking.com inventory prerequisite fails before owner price checks can reach
the qualified Stagehand price executor. Waiting for price promotion before migrating inventory is
therefore circular. Unlike a price observation, inventory perception also carries an asymmetric
absence risk: trusting a model's claim that the account is complete could archive an unseen booking
and stop monitoring it.

The deployment currently has no invited users. The owner explicitly chose to roll agentic inventory
out to every authorized user rather than limiting it to an owner canary, while retaining the
existing disclosure, budget, safety, session, and rollback boundaries.

## Decision

Add a separate provider-neutral `InventoryBrowserExecutor` using local Stagehand semantic
observe/guard/replay/extract and one guarded Anthropic computer-use episode. Route inventory
independently from price and make agentic inventory the default for every disclosed authorized user.
Keep the legacy inventory adapter only as a capability-specific rollback path and never invoke it as
a same-job fallback.

BookSaver accepts only positively observed, validated reservations from the current synchronization
run. Agentic inventory always uses positive-only reconciliation: it can insert or refresh accepted
rows but can never mark an unseen row absent, even when traversal evidence claims completeness.
Only a monitoring projection tied to a positive observation in the exact current run can continue
to price checking.

Bare `/checknow` presents saved caller-owned choices without browser work. The selected operation
then performs one inventory verification and, if admitted by a current-run receipt, one price check
under the same job ID, cost ledger, residual action allowance, and absolute deadline.

## Rationale

- Moving the capability forward removes the circular blocker without weakening transaction safety.
- Positive evidence can validate one known reservation; absence requires a materially stronger
  proof and is unnecessary to resume monitoring.
- Capability-specific routing lets inventory advance without implying price promotion.
- A single selected refresh avoids duplicate latency and Anthropic cost.
- Keeping legacy isolated preserves immediate rollback without making selector parsing authoritative
  inside the agentic path.

## Alternatives Considered

- **Wait for price promotion**: rejected because legacy inventory prevents collecting price-canary
  evidence.
- **Add Stagehand as a legacy parser recovery tier**: rejected because fixed selectors would remain
  the authoritative success path and maintenance blocker.
- **Trust typed model completeness for absence reconciliation**: rejected because false absence can
  silently stop monitoring saved reservations.
- **Owner-only inventory canary**: rejected by the owner because no invited users currently use the
  deployment; disclosure and authorization still apply to future invitees.
- **Run legacy after agentic failure**: rejected because it doubles work and hides whether the new
  capability is reliable.

## Consequences

- Account-wide views may retain a stale unseen reservation until a future separately approved
  absence-authority mechanism exists; Telegram must label preserved state clearly.
- `/checknow` and scheduled work can proceed for freshly re-observed reservations even when the
  account-wide traversal is incomplete.
- Inventory needs its own redacted operational metrics and rollback signal; price-canary records
  remain unchanged.
- Combined inventory and price orchestration must share limits rather than allocating two complete
  jobs.
- `/connect` remains server-verified and Playwright-backed.
