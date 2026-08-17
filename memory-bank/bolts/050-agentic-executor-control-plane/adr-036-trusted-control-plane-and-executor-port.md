---
bolt: 050-agentic-executor-control-plane
created: 2026-08-16T19:18:41Z
status: accepted
---

# ADR-036: Trusted Control Plane and Provider-Neutral Browser Executor Port

## Context

Booking.com presentation changes repeatedly break selector-specific price automation. Making a model
the domain authority would replace visible maintenance with silent correctness and safety risk.

## Decision

BookSaver remains the trusted control plane. A provider-neutral `PriceBrowserExecutor` receives
trusted query facts, an opaque one-job session lease, and exact limits and returns only untrusted
typed evidence plus closed execution metadata. BookSaver independently validates every query and
offer fact and alone decides equivalence, savings, persistence, and notification.

Session values remain inside a transient local browser. The lease is owner/job bound and cleanup is
unconditional. Provider types, cookies, page content, and model reasoning cannot cross the port.

## Alternatives Considered

- **Model declares the best/saving offer**: rejected because it collapses perception and authority.
- **Expose the current Playwright browser port**: rejected because it leaks selector/tool semantics.
- **Cache repaired selectors/actions**: deferred; it adds mutable authority and maintenance machinery.

## Consequences

Adapters remain replaceable and failures are explicit, but typed evidence and validation require
more code. This is accepted because false savings are more harmful than missed observations.
