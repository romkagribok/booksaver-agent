---
stage: model
bolt: 056-agentic-inventory-executor
created: 2026-08-27T23:13:41Z
status: complete
---

# Static Domain Model: Layered Inventory Destination Policy

## Bounded Context

The **Inventory Navigation Safety** context decides whether a browser destination may be rejected,
observed without interaction, or used for guarded task-specific interaction. It sits between the
fixed code-owned Booking.com inventory entry navigation and all Stagehand or computer-use actions.
It does not decide reservation truth, inventory completeness, authentication, or savings.

## Entities

### InventoryBrowserEpisode

- **Identity**: one owner-bound inventory execution ID.
- **Properties**: requested destination, current destination snapshot, navigation phase, task,
  destination disposition, executed action count, and terminal outcome.
- **Rules**:
  - The initial URL remains code-owned and read-only.
  - A destination is evaluated before perception and before and after every action.
  - `observe_only` never implies permission to click, type, submit, download, or open a popup.
  - Any executed prohibited transition terminates the episode fail-closed.

### DestinationDiagnostic

- **Identity**: one rejected destination transition within an execution.
- **Properties**: execution ID, phase, destination class, sanitized path template, sorted query-key
  names, rejection reason, and popup state.
- **Rules**:
  - It contains no raw URL, host outside a closed class, query value, fragment, page content,
    selector, screenshot, cookie, credential, reservation identity, or model text.
  - Every string field is bounded and derived by code before logging.
  - Diagnostics explain safety decisions but never grant action authority.

## Value Objects

### DestinationDisposition

- **Values**: `deny`, `observe_only`, `interact`.
- **Constraints**:
  - Non-HTTPS, non-Booking, user-info, nonstandard-port, known authentication/challenge, known
    account mutation, payment, checkout, purchase, download, or unsafe-popup destinations are
    `deny`.
  - An otherwise non-mutating Booking.com destination whose route is unfamiliar is
    `observe_only`.
  - `interact` additionally requires task-specific, code-verifiable read-only context and inspected
    element metadata; provider descriptions do not contribute authority.

### SanitizedRouteShape

- **Values**: closed host class, bounded path template, sorted unique query-key names, fragment
  presence flag, and destination class.
- **Constraints**:
  - Numeric, UUID-like, opaque, or high-entropy path segments become placeholders.
  - Query values and fragment values are always discarded.
  - Unsafe semantic tokens remain visible only as a closed destination class or rejection reason.

### NavigationPhase

- **Values**: `entry_redirect`, `semantic_pre_action`, `semantic_post_action`,
  `computer_pre_action`, `computer_post_action`.
- **Constraints**: the phase is code-owned and cannot be supplied by a provider.

## Aggregate

### InventoryDestinationPolicy

`InventoryDestinationPolicy` classifies a destination and produces both a disposition and sanitized
route shape. Its invariant is that observation authority is strictly weaker than interaction
authority: accepting benign Booking.com route churn for perception cannot expand the action,
egress, session, or transaction boundary.

## Domain Events

- **DestinationObservedSafely**: an unfamiliar but non-mutating Booking.com destination is admitted
  for perception only.
- **DestinationInteractionAdmitted**: inspected metadata and task context prove a read-only action
  is eligible for replay.
- **DestinationRejected**: a code-owned rule denies a destination or transition and emits one
  sanitized local diagnostic.

These are conceptual runtime events; this bolt adds no event stream or raw browser-state storage.

## Domain Services

- **DestinationClassifier**: converts browser destination metadata into a three-level disposition.
- **InteractionAuthorizer**: combines disposition, task, inspected element metadata, popup state,
  and action vocabulary; it never consumes provider-authored descriptions.
- **DestinationDiagnosticSanitizer**: produces bounded privacy-safe fields for local logging.

## Repository Interfaces

None. Existing content-free inventory execution metrics remain authoritative for persisted run
outcomes; destination diagnostics are local sanitized operational logs unless a later, separately
approved persistence contract is introduced.

## Ubiquitous Language

- **Observation authority**: permission to let the local harness inspect a Booking.com page without
  permitting any browser action.
- **Interaction authority**: narrower permission for BookSaver to replay one guarded read-only
  action supported by inspected metadata and current traversal task.
- **Benign route churn**: provider-controlled path or query variation that stays on HTTPS
  Booking.com and contains no known authentication, challenge, mutation, payment, checkout,
  purchase, or download intent.
- **Sanitized route shape**: a bounded diagnostic representation that preserves useful route
  structure and query-key names while discarding identifiers and all values.
