---
stage: model
bolt: 065-shared-browser-use-access
created: 2026-09-03T23:36:00Z
---

# Static Model: Shared Browser Use Access

## Entities

- **BrowserExecutionAdmission**: One code-owned decision for an active user and future job. It binds
  configured route, user role, current disclosure version, stored acknowledgement, qualification
  state, and one closed reason. It contains no session or page content.
- **AdminUserFundingProjection**: One owner-visible aggregate user row. It contains display identity,
  role, access state, active-booking count, coarse personal legacy-key presence, and the fixed
  Browser Use funding policy; it never contains key or exact domain material.

## Value Objects

- **PriceRoutingMode**: Closed value `legacy`, `owner_canary`, `agentic`, or `consented_users`.
- **DisclosureVersionMatch**: Equality between configured disclosure version and the invitee's
  stored acknowledgement. Missing or stale acknowledgement is not a match.
- **RoutingReason**: Content-free reason describing admitted owner rollout, admitted consented
  invitee rollout, disclosure required, qualification required, configured legacy, or regression.
- **PersonalLegacyKeyPresence**: Boolean derived from encrypted-key nullability. It is not a secret
  representation and supports only `configured` or `not configured` presentation.
- **BrowserUseFundingPolicy**: Fixed statement that agentic Browser Use uses the deployment owner's
  `BOOKSAVER_LLM_API_KEY` for every caller.

## Aggregates

- **Browser Route Admission** (aggregate root): Combines user authorization, route configuration,
  disclosure, qualification, and regression. Invariants: inactive users never reach routing;
  regression dominates every agentic route; `consented_users` never mutates qualification;
  invitees require current consent; one decision applies equally to manual and scheduled price
  work.
- **Owner Administration Projection** (aggregate root): Produces one allowlisted row per local user.
  Invariants: owner-only delivery; aggregate SQL only; no decryption or exact-record
  materialization; funding policy is current-policy truth, not historical per-attempt attribution.

## Domain Events

- **ConsentedUserPriceRouteSelected**: An owner or currently disclosed active invitee is admitted to
  Browser Use under the explicit early-rollout mode.
- **InviteeDisclosureRequired**: An invitee is not admitted because the current disclosure was not
  acknowledged.
- **AgenticRegressionApplied**: A recorded regression routes future jobs to legacy regardless of
  early-rollout configuration.
- **AdminFundingProjectionViewed**: The deployment owner receives secret-safe current funding and
  personal-key-presence labels; this event is conceptual and requires no new persisted audit row.

## Domain Services

- **PriceRouteResolver**: Returns a closed routing decision without constructing an executor or
  changing qualification state.
- **InventoryAdmissionPolicy**: Existing policy admitting Browser Use inventory for the owner and
  currently disclosed active invitees.
- **AdminFundingProjector**: Derives aggregate identity, booking count, and boolean key presence in
  SQL without loading or decrypting exact records.
- **AdminFundingPresenter**: Formats the fixed Browser Use funding policy and coarse personal-key
  state for the owner-only Telegram surface.

## Repository Interfaces

- **DisclosureConsentRepository**: Returns the current stored disclosure version for one user.
- **AgenticQualificationRepository**: Returns qualification/regression state; route resolution is
  read-only.
- **UserAggregateRepository**: Returns only allowlisted admin projection fields, including boolean
  encrypted-key presence.

## Ubiquitous Language

- **Consented-user rollout**: Explicit owner-selected Browser Use admission before statistical
  qualification, limited to current disclosure consent.
- **Qualification-gated route**: Existing `agentic` mode requiring persisted qualified evidence.
- **Funding provenance**: Which configured credential policy pays for future Browser Use calls; not
  the identity or value of a secret.
- **Personal legacy key**: Optional encrypted per-user Anthropic key used only by legacy LLM paths.
- **Key presence**: Whether encrypted key bytes exist. It conveys no bytes, pattern, or validity.

## Story Coverage

- **US-170**: BrowserExecutionAdmission, PriceRoutingMode, DisclosureVersionMatch, RouteResolver,
  regression dominance, and identical manual/scheduled selection.
- **US-171**: AdminUserFundingProjection, PersonalLegacyKeyPresence, BrowserUseFundingPolicy,
  aggregate repository, and owner-only presentation.
