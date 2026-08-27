---
id: ADR-040
title: Separate destination observation from interaction authority
status: accepted
created: 2026-08-27T23:17:21Z
bolt: 056-agentic-inventory-executor
---

# ADR-040: Separate Destination Observation from Interaction Authority

## Context

The first live agentic inventory run launched local Stagehand and completed the fixed Booking.com
navigation, but BookSaver terminated before semantic extraction because the final destination did
not match an exact inventory path and closed query-key allowlist. This made provider route churn a
code-maintenance boundary equivalent to the selectors the agentic executor was intended to replace.

Removing destination validation entirely would be unsafe. The browser holds an authenticated
Booking.com session, model-visible pages can contain prompt injection, and Booking.com also exposes
account mutation, cancellation, reservation, checkout, and payment surfaces.

## Decision

Separate destination **observation authority** from **interaction authority**.

A fixed code-owned inventory navigation may expose an unfamiliar destination to Stagehand only when
it remains HTTPS on Booking.com, has no user information or nonstandard port, opens no unexpected
popup, and contains no known authentication, challenge, mutation, cancellation, reservation,
checkout, payment, purchase, or download intent. Exact path names and benign query-key sets are not
security boundaries.

An observable destination does not become generally interactive. BookSaver admits each action only
when the current traversal task and inspected browser metadata prove a scope, pagination, or detail
operation; provider descriptions remain non-authoritative. Current, target, and post-action
destinations are reassessed, and any unsafe executed transition terminates the episode.

Rejected destinations emit a bounded local diagnostic containing a closed host/category, sanitized
path template, sorted query-key names, fragment-presence flag, phase, and reason. Raw URLs, values,
fragments, page content, selectors, cookies, credentials, reservation identities, and model text are
never logged or persisted.

## Rationale

- Benign Booking.com route/query churn can reach semantic perception without code updates.
- Observation alone cannot click or mutate account state.
- Task-specific inspected evidence retains a code-owned authorization boundary for every action.
- A sensitive-route denylist changes much less often than an exact inventory-route allowlist and
  fails closed when risk-signaling terms appear.
- Sanitized route shape makes live failures actionable without weakening ADR-034 privacy rules.

## Alternatives Considered

- **Drop all destination checks**: rejected because prompt injection or model error could reach
  authenticated mutation and payment surfaces.
- **Keep exact paths but allow arbitrary query keys**: rejected because path churn would still block
  Stagehand before perception.
- **Let the model classify safe pages**: rejected because provider output cannot grant browser
  authority.
- **Persist raw rejected URLs**: rejected because URLs can contain account, reservation, tracking,
  or session-linked identifiers.
- **Treat every unknown Booking.com page as fully interactive**: rejected because same-domain
  confinement alone does not prevent account mutation.

## Consequences

- The destination policy becomes a layered classifier rather than a small exact allowlist.
- Sensitive-route terminology remains code-maintained, but ordinary read-only route and tracking
  churn no longer requires updates.
- Some unfamiliar pages may be observed and then stop if no task-specific action can be proven;
  this is a safe inconclusive outcome rather than blanket authorization.
- Local logs become materially more useful while remaining unsuitable for reconstructing a raw URL
  or reservation identity.
- Live Telegram acceptance remains necessary because offline fixtures cannot prove Booking.com's
  actual redirect and rendered account behavior.
