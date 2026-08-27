---
stage: design
bolt: 056-agentic-inventory-executor
created: 2026-08-27T23:16:47Z
status: complete
---

# Technical Design: Layered Inventory Destination Policy

## Architecture Pattern

Retain the existing local Stagehand adapter and introduce a pure code-owned destination-policy
layer with two distinct decisions:

1. **Observation admission** decides whether the fixed inventory navigation may expose the page to
   semantic extraction.
2. **Interaction admission** decides whether one task-specific inspected action may be replayed and
   whether its resulting destination remains acceptable.

This is an infrastructure safety policy under BookSaver's trusted control plane. Provider output
may propose an element but cannot change destination classification, diagnostic fields, or action
authority.

## Layer Structure

- **Domain/application contracts**: unchanged. Inventory observations, validation, positive-only
  reconciliation, session leases, and execution limits retain their existing interfaces.
- **Infrastructure browser policy**: classify destinations, sanitize route shapes, authorize
  task-specific actions, and emit local diagnostics.
- **Infrastructure Stagehand adapter**: call observation admission after fixed entry navigation;
  call interaction admission before and after semantic or coordinate actions.
- **Persistence**: unchanged. Existing inventory terminal status, usage, cost, latency, fallback,
  and safety codes remain the only persisted execution metadata.
- **Operations**: local warning logs receive bounded sanitized destination diagnostics.

## Internal Contracts

### DestinationAssessment

- `disposition`: `deny | observe_only | interact`
- `category`: closed machine code such as `inventory`, `confirmation`, `authentication`,
  `challenge`, `mutation`, `unknown_booking`, `external`, or `invalid`
- `host_class`, `path_template`, `query_keys`, and `fragment_present`: bounded diagnostic shape
- `terminal_status`: optional existing inventory terminal status for authentication/challenge pages

### SanitizedRouteShape

- `host_class`: `secure_booking | account_booking | www_booking | other_booking | external | invalid`
- `path_template`: bounded to a maximum of eight closed-vocabulary components; all other segments
  become `{segment}`
- `query_keys`: sorted, unique, normalized key names, bounded in count and length
- `fragment_present`: boolean only

### DestinationPolicy Operations

- `assess_observation(snapshot, phase) -> DestinationAssessment`
- `assess_interaction(proposal, task, phase) -> DestinationAssessment`
- `diagnostic(execution_id, assessment, phase) -> bounded log fields`

No provider-authored description enters these operations.

## Classification Algorithm

1. Parse with the standard-library URL parser and reject malformed destinations.
2. Require HTTPS, no user information, the default HTTPS port, and Booking.com or a subdomain.
3. Examine normalized path, non-date query keys, control-query values, and fragment only in memory.
   Ordinary stay-date fields such as `checkin` and `checkout` are data, not action signals. Known
   authentication/MFA/captcha/bot-wall families map to existing typed terminal outcomes. Known
   account mutation, cancellation, reservation, checkout, payment, purchase, or download families
   are denied.
4. Treat only strong account-inventory and confirmation route families as interactive candidates
   without requiring a closed set of benign query keys. Generic `/booking`-style pages remain
   observation-only.
5. Treat other non-mutating Booking.com destinations as `observe_only`, allowing semantic state
   extraction but no generic action.
6. Permit one action only when inspected role/label/href and the code-owned inventory traversal task
   prove it is a scope, pagination, or detail operation and both current and target destinations are
   non-denied. Detail clicks additionally require a real href plus confirmation-route or exact
   reservation-subject evidence. Unknown routes therefore gain no blanket interaction capability.
7. Reassess the resulting destination after every action. Unsafe transitions and new popups remain
   terminal.

## Diagnostic Sanitization

- Preserve a small allowlist of harmless static path characters and slugs.
- Replace numeric, UUID-like, long, token-like, percent-encoded opaque, or otherwise high-entropy
  path segments with `{id}`.
- Retain normalized query-key names only; discard every value before formatting.
- Retain fragment presence only; discard its value.
- Map hosts to a closed class instead of logging arbitrary hostnames.
- Bound every field and use structured key/value logging with no exception text derived from page
  content or provider responses.
- Emit diagnostics on denied entry navigation and denied pre/post-action transitions. Do not log
  successful page content or every accepted destination.

## Data Model

No schema migration. Raw or sanitized destinations are not added to SQLite. Existing
`agentic_inventory_executions.safety_codes_json` continues to persist only closed safety codes.

## Security Design

- **Egress**: unchanged Booking.com, Anthropic, and loopback boundary.
- **Navigation**: the only direct navigation remains BookSaver's fixed HTTPS inventory entry URL;
  providers receive no arbitrary navigation tool.
- **Actions**: existing closed vocabulary, hit testing, task matching, mutation label denylist,
  popup checks, download prohibition, and pre/post checks remain binding.
- **Unknown pages**: observation is allowed only on Booking.com; interaction remains action-specific
  and code-authorized.
- **Prompt injection**: model descriptions are ignored for authorization; inspected browser
  metadata and code-owned task context are required.
- **Privacy**: raw URLs and values live only transiently inside the classifier and are never logged,
  persisted, prompted as diagnostic context, or returned through executor contracts.

## Failure Semantics

- Known authentication and challenge destinations retain precise typed terminal outcomes.
- Denied entry destinations return the existing unsafe terminal with a closed safety code and one
  sanitized warning.
- A rejected semantic proposal remains eligible for the existing guarded visual fallback when no
  unsafe transition was executed.
- A post-action unsafe transition remains terminal and cannot fall back.

## NFR Implementation

- **Maintainability**: benign route/query additions require no code change; only new sensitive route
  families may require denylist maintenance.
- **Performance**: classification and sanitization are synchronous bounded string operations and add
  no browser or model calls.
- **Cost**: rejected destinations still consume no model tokens; admitted pages remain subject to
  the existing exact ledger and limits.
- **Observability**: every destination rejection explains phase, category, sanitized route shape,
  and reason in local logs.
- **Compatibility**: no executor-port, config, database, Telegram, or session format changes.

## Verification Plan

- Unit-test URL parsing, three-level disposition, terminal classification, action-specific
  authorization, sanitizer bounds, and log redaction.
- Add regressions for benign tracking keys, changed inventory paths, fragments, hyphenated sign-in
  paths, mutation query keys/values, external hosts, HTTP, user-info, nonstandard ports, popups, and
  post-action transitions.
- Exercise the adapter with a benign unfamiliar Booking.com entry destination and prove semantic
  extraction is reached.
- Assert diagnostics contain no raw URL, query value, fragment value, reservation-like identifier,
  cookie, page text, selector, or provider description.
- Run focused inventory/security tests, Ruff, mypy, the full test suite, AI-DLC validators, and exact
  Docker Stagehand smoke before merge.
