---
stage: design
bolt: 058-agentic-inventory-executor
created: 2026-08-28T01:25:00Z
---

# Technical Design: Provider-Compatible Agentic Inventory Schemas

## Architecture Pattern

Keep the existing provider-neutral executor, Stagehand runtime, Anthropic fallback, and trusted
validator. Add provider-specific wire projections only inside the browser adapter. Decode those
projections back into the unchanged inventory domain types before returning from infrastructure.

This is an adapter compatibility correction under ADR-036, ADR-037, ADR-039, and ADR-040, not a new
architecture or authority decision.

## Layer Structure

- **Domain**: No changes to inventory observations, evidence completeness, limits, safety outcomes,
  or positive-only reconciliation.
- **Application**: No executor-port, validation, routing, or persistence changes.
- **Stagehand adapter**: Represent the four tri-state scope flags (`authenticated`, visible scope,
  explicit empty, pagination exhausted) as required string enums `true`, `false`, or `unknown` on
  the wire. Decode them to `bool | None`. This removes four union parameters and leaves at most 14.
- **Anthropic adapter**: Project unsupported constraint keywords out of computer-use tool
  declarations. Keep the simple terminal tool strict; submit the large observation tool non-strict
  because it exceeds Anthropic's aggregate grammar-size ceiling, then reject invalid or excessive
  scope/reservation data immediately in trusted parsing before mapping items.
- **Diagnostics**: Normalize known schema rejections into closed content-free categories and log
  only execution ID, provider phase, category, and exception class.

## API Design

- No public CLI, Telegram, executor-port, or provider selection changes.
- Stagehand wire tri-state: `"true" | "false" | "unknown"`.
- Internal decoded tri-state: `True | False | None`.
- Computer submission remains the same logical typed tool contract; provider conformance is treated
  as advisory for the large observation schema, and all constraints remain authoritative in trusted
  decoding because the endpoint rejects `maxItems` and cannot compile the full strict grammar.

## Data Model

- No database schema or migration changes.
- No prompt, provider error body, page content, screenshot, selector, URL, cookie, or reasoning is
  persisted.
- Existing execution/cost rows remain authoritative for terminal status and conservative spend.

## Security Design

- Treat every model tool input as untrusted regardless of the provider's strict flag. Validate raw
  arrays are actual non-string sequences and enforce exact scope and bounded
  reservation counts before iterating or constructing domain objects.
- Keep all existing per-field Pydantic constraints and domain constructors.
- Unknown tri-state values fail decoding rather than becoming truthy or inferred evidence.
- Provider exception text may be inspected locally only for closed-category classification and is
  never logged or persisted.
- No action, destination, authentication, session, budget, timeout, or reconciliation guard changes.

## NFR Implementation

- **Reliability**: Offline regression inspects generated schemas and reproduces both provider
  rejection predicates without network calls.
- **Observability**: Known schema failures produce distinct redacted categories instead of the
  undifferentiated provider failure currently shown in persisted outcomes.
- **Maintainability**: Centralize tri-state encode/decode and collection bounds beside existing
  adapter constants; avoid provider-specific types outside infrastructure.
- **Cost**: Rejections are detectable before live canary, avoiding conservative reservations and
  zero-token provider failures.

## Verification Plan

1. Assert the Stagehand scope schema contains no more than 16 union/nullable parameters and maps all
   three tri-state values correctly.
2. Assert every Anthropic computer-use tool schema omits `maxItems` and oversized submitted arrays
   fail before mapping.
3. Assert known Stagehand and Anthropic schema messages map to closed diagnostic codes while raw
   messages never appear in logs.
4. Run focused inventory adapter tests, related executor/coordinator tests, Ruff, mypy, full pytest,
   AI-DLC validators, Bugbot, exact-image cookie-free smoke, and production health verification.
