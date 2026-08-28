---
stage: model
bolt: 058-agentic-inventory-executor
created: 2026-08-28T01:24:00Z
---

# Static Model: Provider-Compatible Agentic Inventory Schemas

## Entities

- **Inventory observation**: Existing typed positive reservation and scope evidence. Its identity,
  lifecycle, pricing, refundability, occupancy, and completeness rules remain unchanged.
- **Semantic extraction contract**: The typed request/response shape submitted through Stagehand.
  It must be representable within the runtime's bounded union-parameter compiler.
- **Computer-use tool contract**: The typed action, submission, and terminal tools submitted to
  Anthropic. It must use the endpoint's supported JSON Schema subset.

## Value Objects

- **Provider schema profile**: Provider/runtime name, schema capability limits, and a bounded
  compatibility failure code. It contains no prompt, page, screenshot, response body, or session
  content.
- **Bounded collection**: A decoded tuple whose maximum length is enforced by BookSaver code even
  when a provider schema cannot express `maxItems`.
- **Optional evidence group**: Related optional observation facts represented as a nested object so
  Stagehand's top-level compiled schema stays within its union-parameter limit.

## Aggregates

- **Agentic inventory execution**: Existing session-bound, action-bounded, deadline-bounded, and
  cost-bounded execution plus its provider-compatible schemas. Invariants: provider syntax cannot
  weaken domain validation; untrusted output is decoded and bounded before it becomes an observed
  reservation; unseen reservations never become absent.

## Domain Events

- **Provider schema rejected**: Content-free execution event containing execution identifier,
  semantic or computer-use phase, provider schema profile, and a closed failure category.
- **Inventory observation submitted**: Existing typed observation event after provider decoding and
  BookSaver validation.

## Domain Services

- **Schema projection**: Maps the unchanged inventory evidence vocabulary into a provider-supported
  wire shape.
- **Observation decoding**: Restores the unchanged typed inventory facts, enforces collection/value
  bounds, and rejects conflicts or excess items before reconciliation.

## Repository Interfaces

- No new repository interface. Existing redacted execution metrics retain terminal status, usage,
  cost, latency, fallback, and bounded safety/failure codes only.

## Ubiquitous Language

- **Schema compatibility**: A provider accepts the declared wire schema before inference.
- **Wire bound**: A constraint expressible in the provider's JSON Schema subset.
- **Code-owned bound**: The same or stricter constraint enforced during trusted decoding when the
  provider cannot express it.
- **Pre-inference rejection**: Provider/runtime refusal caused by schema syntax or compilation,
  before any model tokens are consumed.
- **Fail closed**: Return a typed provider failure and accept no evidence when schema projection or
  decoding fails.

## Story Coverage

- US-158 is covered by provider-supported wire projections, code-owned bounds, content-free schema
  rejection events, and unchanged inventory aggregate invariants.
