---
unit: 006-browser-use-price-executor
intent: 023-replaceable-agentic-browser-executor
phase: construction
status: in-progress
created: 2026-09-02T23:44:45Z
updated: 2026-09-03T00:36:00Z
unit_type: backend
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: Browser Use Price Executor

## Purpose

Make local Browser Use the default price executor for both owner `/checknow` and scheduled checks
without transferring price, equivalence, savings, session, or transaction authority out of
BookSaver. Preserve Stagehand and the deterministic path as explicit future-job rollback choices.

## Scope

### In Scope

- A local Browser Use implementation of the existing `PriceBrowserExecutor`.
- One shared price route for manual and scheduled checks.
- Guarded human-like actions with trusted-value typing and typed price submission.
- Browser/model-view preflight and content-free runtime diagnostics.
- Browser Use-specific qualification identity and canary cost thresholds.
- Explicit Browser Use, Stagehand, and deterministic rollback selection without same-job fallback.
- An operator-only production-equivalent price replay using isolated state.
- Browser Use for the current-run inventory prerequisite of every price operation.

### Out of Scope

- Automatic Browser Use-to-Stagehand fallback.
- Selecting Stagehand as the optimized primary before comparative production evidence exists.
- Browser Use Cloud, managed browsers, new model providers, local GPUs, or cached action learning.
- Changes to `/connect`, equivalence, savings, or notification policy.
- Legacy selector removal before qualification and the approved rollback window.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-13 | Browser Use as the default price executor | Must |
| FR-14 | Guarded Browser Use price operation | Must |
| FR-15 | BookSaver-owned price evidence acceptance | Must |
| FR-16 | Model-view preflight and redacted diagnostics | Must |
| FR-17 | Explicit Stagehand and deterministic rollback | Must |
| FR-18 | Browser Use-specific price qualification | Must |
| FR-19 | Production-equivalent price replay | Must |
| FR-20 | Browser Use for price-operation inventory prerequisites | Must |

## Domain Concepts

- **PriceExecutorSelection**: Code-owned choice of Browser Use, Stagehand, or deterministic routing
  for a future job; never a model decision.
- **BrowserUsePriceEpisode**: One bounded local agent run against an owner-bound transient session.
- **ModelViewPreflight**: Content-free proof that the selected browser context and representation are
  usable before paid inference.
- **TypedPriceObservation**: Provider-neutral untrusted query facts and visible offers submitted for
  BookSaver validation.
- **PriceReplay**: Operator-only execution through the deployed `/checknow` coordinator path with
  notifications disabled and normal BookSaver validation/audit persistence retained.

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 6 |
| Must Have | 6 |
| Should Have | 0 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-164 | Default manual and scheduled price checks to Browser Use | Must | Planned |
| US-165 | Execute a guarded typed Browser Use price episode | Must | Planned |
| US-166 | Diagnose the model-visible page before paid inference | Must | Planned |
| US-167 | Preserve explicit rollback and qualify Browser Use independently | Must | Planned |
| US-168 | Replay the deployed price path without Telegram | Must | Planned |
| US-169 | Remove the Stagehand inventory prerequisite from price operations | Must | Planned |

## Dependencies

- Unit 001 provider-neutral port, session lease, limits, and BookSaver validation boundary.
- Unit 002 Stagehand price adapter retained as rollback.
- Unit 003 qualification ledger and promotion/regression policy.
- Unit 004 pinned Browser Use runtime, confinement, mobile context, and guarded-tool patterns.
- Existing coordinator, scheduler, encrypted session vault, and isolated replay conventions.

## Constraints

- Browser Use is untrusted and receives no cookie values, credentials, or transaction tools.
- Manual and scheduled price execution cannot diverge after route selection.
- A failed Browser Use job cannot cascade to a second browser harness in the same operation.
- No Booking.com CSS selector, test ID, or exact DOM nesting enters the new adapter.
- Content-bearing model inputs remain ephemeral and absent from persisted diagnostics.

## Success Criteria

- [ ] `/checknow` and scheduled tests resolve the same Browser Use executor.
- [ ] Complete typed observations pass the existing validator; ambiguous evidence fails closed.
- [ ] Every physical action, destination, value, cost, and deadline remains code-guarded.
- [ ] Preflight rejects unusable model views before paid inference whenever detectable.
- [ ] Stagehand and deterministic routes remain explicit rollback choices only.
- [ ] Exact-container replay waits for Browser Use and exits zero only on an accepted observation.

## Bolt Suggestions

- `064-browser-use-price-executor`: US-164 through US-169 after bolt 063.
