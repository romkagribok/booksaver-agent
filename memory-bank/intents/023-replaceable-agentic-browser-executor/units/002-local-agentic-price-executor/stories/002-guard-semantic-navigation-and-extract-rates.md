---
id: 002-guard-semantic-navigation-and-extract-rates
unit: 002-local-agentic-price-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: '2026-08-16T19:18:41Z'
assigned_bolt: 051-local-agentic-price-executor
implemented: true
---

# Story: Guard Semantic Navigation and Extract Typed Rates

## User Story

**As a** BookSaver user
**I want** semantic navigation resilient to ordinary DOM churn
**So that** price checks do not depend on BookSaver-owned Booking selectors

## Acceptance Criteria

- [x] Every Stagehand action follows observe, code preview guard, deterministic replay, and post-check.
- [x] Typed extraction returns only contract-shaped property/query/auth/rate facts.
- [x] Direct unreviewed actions, action caching, self-healing selector persistence, and generated code
  repair are disabled.
- [x] Semantic failure hands the same browser to one bounded fallback or returns a typed outcome.

## Dependencies

- US-143 through US-147 and existing Booking destination policy.

## Out of Scope

- Equivalence or savings decisions.
