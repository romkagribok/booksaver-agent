---
stage: model
bolt: 052-agentic-browser-qualification
created: 2026-08-17T04:19:00Z
status: complete
---

# Static Domain Model: Agentic Browser Qualification

## Bounded Context

The **Agentic Browser Qualification** context decides whether real owner evidence is sufficient to
make the already-built agentic price capability available to consenting invited users. It consumes
only redacted check outcomes and never browser content. It cannot execute a browser, synthesize live
evidence, or make a promotion decision without an explicit local owner action.

## Aggregates

### OwnerCanary

- **Identity**: deployment owner user ID plus unique BookSaver check IDs.
- **Evidence**: observation time, eligibility/unblocked flag, valid-observation flag, optional manual
  correctness result, reconciled model cost, duration, fallback use, and closed critical violations.
- **Invariants**:
  - Only the active owner may append canary evidence.
  - Manual comparison can target only a valid persisted owner observation.
  - Page content, screenshots, trees, prompts, reasoning, cookies, and selectors are not fields.
  - Evidence is append-only except for the explicit manual verdict on one existing check.

### AgenticPromotion

- **Identity**: singleton deployment policy `agentic-price-v1`.
- **States**: `unqualified`, `qualified`, or `regressed`.
- **Invariants**:
  - The repository reevaluates its own persisted evidence; callers cannot pass a verdict.
  - Qualification requires every exact threshold and explicit owner execution of promotion.
  - Qualification records a 30-day rollback deadline.
  - A critical violation or three consecutive eligible invalid observations inside that window
    changes state to `regressed` before the next route is resolved.

### DisclosureConsent

- **Identity**: invited local user ID.
- **Properties**: current disclosure version and acknowledgement time.
- **Invariants**:
  - Only an active invited user may acknowledge.
  - A new disclosure version invalidates an older acknowledgement for routing.
  - Consent never contains Booking.com or Anthropic content.

## Domain Services

`evaluate_agentic_canary` deterministically calculates nearest-rank p95 metrics and every promotion
blocker. `resolve_execution_route` remains the final fail-closed consumer of promotion state and
current consent.
