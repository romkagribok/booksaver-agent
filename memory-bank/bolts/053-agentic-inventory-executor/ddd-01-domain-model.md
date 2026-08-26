---
stage: model
bolt: 053-agentic-inventory-executor
created: 2026-08-26T03:37:34Z
---

# Static Model: Agentic Inventory Executor

## Bounded Context

The Inventory Perception context observes authenticated Booking.com reservation facts through a
replaceable read-only browser executor. It does not own account truth, monitoring eligibility,
absence reconciliation, price evaluation, session authority, or notifications. Those remain in the
BookSaver control plane.

## Entities

- **Inventory Execution**: One authorized, bounded account observation attempt. It is identified by
  execution ID, bound to one user/account session subject, and constrained by one deadline, action
  allowance, and cost allowance.
- **Observed Reservation**: Positive visible evidence for one stable remote reservation identity.
  It may contain lifecycle, property, dates, room, occupancy, booked total, currency,
  refundability, deadline, and evidence states. It cannot declare eligibility or absence.
- **Scope Observation**: Evidence from one required lifecycle scope (`upcoming`, `past`, or
  `cancelled`), including visible state, positive identities, pages visited, and terminal traversal
  evidence. It cannot make account-wide completeness authoritative.
- **Inventory Execution Result**: A terminal envelope containing typed observations and redacted
  operational metadata, or a closed non-observation outcome.
- **Fresh Observation Receipt**: A BookSaver-owned association between an accepted reservation and
  the current synchronization run. Only this receipt may unblock a price check.

## Value Objects

- **Inventory Execution Request**: Execution ID, owner user ID, fixed required scopes, opaque
  account-bound session lease, and shared execution limits.
- **Inventory Session Subject**: Capability-neutral lease binding for `account:<owner-user-id>`;
  price bindings continue to use their booking subject.
- **Observed Reservation Identity**: Stable remote identity plus visible identity evidence. Missing
  or conflicting identity is rejected rather than synthesized.
- **Observed Reservation Facts**: Optional explicitly evidenced lifecycle, property, dates, room,
  occupancy, total/currency, refundability text/deadline, and evidence completeness.
- **Traversal Evidence**: Scope, page, pagination, and detail coverage counts and closed evidence
  states. It is useful for diagnostics but cannot authorize absence in this unit.
- **Inventory Terminal Status**: Observed, signed out, MFA required, captcha, bot wall, unavailable,
  unsafe action, action limit, cost limit, timeout, provider failure, or validation failure.
- **Positive-Only Reconciliation Policy**: Allows validated current-run upserts and forbids unseen
  transitions regardless of traversal claims.
- **Current-Run Eligibility**: A booking may proceed only when its source reservation was accepted
  under the exact synchronization run being evaluated.

## Aggregates

- **Inventory Execution Aggregate**
  - Members: request, account-bound session lease, action meter, cost meter, semantic episode,
    optional computer-use episode, result.
  - Invariants: one owner, one session subject, one absolute deadline, at most 15 total actions, at
    most six computer actions, at most USD 1 job exposure, no session material in observations, and
    unconditional browser teardown.
- **Account Synchronization Aggregate**
  - Members: synchronization run, accepted positive observations, preserved prior rows, derived
    monitoring projections, and fresh observation receipts.
  - Invariants: only validated stable identities upsert; unseen rows remain unchanged; only
    current-run receipts authorize checking; eligibility remains BookSaver-derived.

## Domain Services

- **Inventory Observation Validator**: Validates terminal invariants, account/session binding,
  identity uniqueness, fact evidence, duplicate consistency, allowed lifecycle scopes, and content
  exclusion. Produces accepted positive reservation facts plus rejection counts.
- **Positive Inventory Reconciler**: Applies accepted current-run observations without invoking
  absence reconciliation and exposes the exact fresh reservation identities for downstream checks.
- **Inventory Route Resolver**: Selects agentic inventory for disclosed authorized users and legacy
  inventory only when the capability-specific rollback setting is active. Price routing is not
  consulted.
- **Inventory Action Guard**: Allows only read-only scope, pagination, detail, scroll, safe-key,
  wait, and zoom behavior on approved account routes. It rejects typing and every authentication,
  modification, cancellation, reservation, and payment action.
- **Single-Refresh Check Admission**: Builds a picker from saved caller-owned state, performs one
  selected inventory execution, and admits price execution only for a matching fresh receipt while
  sharing the outer cost ledger and deadline.

## Domain Events

- **InventoryExecutionCompleted**: Redacted terminal status, coverage counts, accepted/rejected
  counts, usage, latency, fallback flag, and safety codes.
- **ReservationPositivelyObserved**: Stable reservation identity accepted for the current run.
- **CurrentRunCheckAdmitted**: Selected booking matches a positive observation receipt.
- **CurrentRunCheckRejected**: Selected booking is missing, conflicting, stale-only, or otherwise
  ineligible in the current run.
- **InventoryCapabilityRegressed**: Critical safety/privacy/session failure or configured reliability
  response returns only inventory routing to legacy.

## Repository Interfaces

- **Account Reservation Repository**: Reconcile positive observations, list caller-owned saved
  state, and return reservation/booking identifiers positively observed in an exact run.
- **Inventory Execution Metrics Repository**: Persist content-free execution metrics and critical
  outcomes without page content or raw reservation identity evidence.
- **Session Lease Broker**: Issue, resolve, consume, and revoke opaque capability-neutral subjects
  without exposing cookies across the executor port.
- **Cost Ledger**: Reserve and reconcile provider exposure for inventory and price attempts under a
  shared job identifier.

## Ubiquitous Language

- **Positive observation**: Explicit visible evidence for one stable reservation; never an inference
  from absence.
- **Last-safe inventory**: Previously persisted observations retained when the current run is partial
  or failed.
- **Fresh receipt**: BookSaver-owned proof that a reservation was accepted in the exact current run.
- **Positive-only reconciliation**: Upsert accepted observations while preserving every unseen row.
- **Capability-specific route**: Independent routing decision for inventory or price execution.
- **Semantic episode**: Stagehand typed extraction and observe/guard/replay navigation.
- **Visual fallback**: One bounded computer-use continuation on the same transient browser.

## Story Coverage

US-153 is covered by the executor/result model, session subject, positive-only reconciliation,
fresh-receipt admission, action guard, capability routing, metrics, and single-refresh orchestration.
