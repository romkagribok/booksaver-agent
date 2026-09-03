---
id: ADR-043
title: Browser Use default price execution with explicit rollback
status: accepted
created: 2026-09-03T00:00:00Z
bolt: 064-browser-use-price-executor
---

# ADR-043: Browser Use Default Price Execution with Explicit Rollback

## Context

BookSaver's provider-neutral price port and validation boundary are implemented, but the active
agentic adapter uses Stagehand semantic extraction plus custom Anthropic computer use. Repeated live
inventory work showed that maintaining harness-specific recovery before useful evidence is costly.
The local Browser Use `/bookings` slice has now completed an authenticated live discovery and
demonstrated that its full agent loop can operate inside BookSaver's local session, guard, cost, and
positive-evidence boundaries.

The owner wants Browser Use to handle current price checks immediately for both manual and scheduled
work. Stagehand may still become a cheaper primary or useful fallback after measurement, but chaining
two harnesses inside one job would mask reliability, double work, and complicate exact limits.

## Decision

Use the exactly pinned local Browser Use OSS adapter as the default implementation of
`PriceBrowserExecutor` for every admitted owner-canary price check, whether initiated by `/checknow`
or the scheduler. Keep route admission separate from adapter selection so invited users still
require qualification and disclosure.

Retain Stagehand as an explicit operator-selectable adapter for future jobs and retain the
deterministic path through the approved rollback window. A Browser Use terminal is final for its
job; BookSaver never invokes another harness after failure in the same operation.

Browser Use receives only a BookSaver-owned closed price action registry, exact trusted query values,
the opaque owner-bound session lease, and residual job limits. Its typed output remains untrusted and
must pass the unchanged BookSaver price validator, equivalence policy, and savings pipeline.

Introduce a model-view preflight that checks the exact Browser Use-owned context, settled destination,
and usable visual or semantic representation before paid inference whenever possible. Persist only
closed content-free measurements and outcomes. Version Browser Use price qualification independently
from Stagehand, accept up to USD 0.25 average during the owner canary, retain USD 0.10 average for
invited-user promotion, and require a production-equivalent isolated replay before release acceptance.

## Alternatives Considered

- **Keep Stagehand primary and Browser Use fallback**: deferred because it preserves the current
  first-hop failure surface and pays for two harnesses when Stagehand fails.
- **Browser Use primary with automatic Stagehand fallback**: deferred because it masks Browser Use
  qualification, complicates terminal evidence, and can duplicate cost and time.
- **Remove Stagehand immediately**: rejected because explicit rollback and later cost comparison have
  value while Browser Use price behavior is newly deployed.
- **Route only `/checknow` through Browser Use**: rejected because manual and scheduled checks already
  share the same trusted price pipeline and trigger-specific adapter behavior would create an
  unqualified divergence.
- **Allow existing Stagehand canary evidence to qualify Browser Use**: rejected because harness,
  prompt, action, and model-view behavior differ materially.
- **Use Browser Use stock tools**: rejected because they exceed BookSaver's read-only authenticated
  browser authority.

## Consequences

### Positive

- Ordinary Booking.com DOM, label, and nesting churn no longer maps to BookSaver-maintained price
  selectors or a trigger-specific price executor.
- Manual and scheduled behavior remain structurally identical.
- Failures remain visible, single-harness, bounded, and attributable.
- Stagehand can be benchmarked later without changing domain policy or booking data.
- Preflight and isolated replay reduce the chance of declaring success from startup-only evidence.

### Negative

- Routine checks incur Browser Use agent cost until a cheaper qualified strategy is proven.
- Browser Use API, browser context, prompts, and guarded-tool integration still require maintenance;
  the system is not maintenance-free.
- A Browser Use failure misses the current observation rather than attempting an automatic fallback.
- Qualification evidence restarts under a new policy identity.

## Relationship to Existing Decisions

- **ADR-036 preserved**: the provider-neutral port and BookSaver authority remain unchanged.
- **ADR-037 amended**: Stagehand remains supported but is no longer the default price adapter.
- **ADR-038 amended**: Browser Use owner canary permits USD 0.25 average while invited-user
  promotion retains USD 0.10 and all correctness/safety gates.
- **ADR-040 preserved**: observation authority does not grant interaction authority.
- **ADR-041 expanded**: the pinned local Browser Use confinement pattern now serves price execution
  in addition to `/bookings` inventory.
- **ADR-042 preserved**: Booking-required AWS WAF token hosts remain subresource-only.

## Validation

- Unit and integration tests for default/explicit executor selection across manual and scheduled jobs.
- Guard, trusted-value, typed-evidence, terminal mapping, cost, timeout, privacy, and teardown tests.
- Model-view preflight tests, including empty semantic state with usable visual evidence and blank
  visual state with zero paid calls.
- Policy-version and dual cost-threshold qualification tests.
- Exact-container startup and isolated VPS price replay that waits for BookSaver validation.
