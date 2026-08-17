---
bolt: 052-agentic-browser-qualification
created: 2026-08-16T19:18:41Z
status: accepted
---

# ADR-038: Owner-Only Canary, Consented Promotion, and Rollback Window

## Context

Fixture success cannot prove authenticated Booking.com reliability, safety, or cost. Invited users
must not become involuntary test traffic, and the current path is needed for rollback during
qualification.

## Decision

Routing is closed to `legacy`, `owner_canary`, and `agentic`; legacy is default. Owner canary admits
only the owner. Invited-user agentic routing requires all offline gates, 30 owner checks over at
least 14 days, 10 correct manual comparisons, at least 95% valid eligible observations, average cost
at most USD 0.10, p95 cost at most USD 0.50, p95 duration at most 180 seconds, fallback at most 20%,
zero critical violations/cap breaches, explicit owner promotion, and current user disclosure consent.

Any safety/privacy/price correctness violation returns routing to legacy during the 30-day rollback
window. Reliability regression is defined as three consecutive eligible invalid observations during
that window and has the same effect. Legacy receives no selector maintenance after promotion and is
removed only by a later release decision if unused.

## Alternatives Considered

- **Immediate invited-user rollout**: rejected; there is no live evidence.
- **Automatic promotion on aggregate metrics**: rejected; manual price comparison and owner approval
  are required.
- **Maintain both paths indefinitely**: rejected because it preserves the maintenance burden.

## Consequences

Promotion takes at least 14 days and requires owner work. In exchange, the deployment has observable
evidence, user consent, and a bounded rollback path.
