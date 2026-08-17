---
id: 001-define-executor-evidence-contract
unit: 001-agentic-executor-control-plane
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: '2026-08-16T19:18:41Z'
assigned_bolt: 050-agentic-executor-control-plane
implemented: true
---

# Story: Define the Executor Evidence Contract

## User Story

**As a** BookSaver maintainer
**I want** a provider-neutral typed executor port
**So that** browser harnesses can be replaced without changing trusted domain policy

## Acceptance Criteria

- [x] Requests contain only trusted query facts, an opaque owner-bound lease, and exact limits.
- [x] Results contain closed status, typed facts/offers, redacted provenance, usage/cost/latency, and
  fallback/session-refresh metadata.
- [x] Offers never declare equivalence or savings, and provider/session types cannot cross the port.
- [x] A fake executor deterministically covers every status and malformed-evidence case.

## Dependencies

- Existing booking, occupancy, money, session, and model-usage types.

## Out of Scope

- Provider integration and production routing.
