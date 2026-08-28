---
id: 004-use-provider-compatible-agentic-schemas
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-08-28T01:23:00Z
assigned_bolt: 058-agentic-inventory-executor
implemented: true
---

# Story: Use Provider-Compatible Agentic Schemas

## User Story

**As a** BookSaver deployment owner
**I want** Stagehand extraction and Anthropic computer-use tools to use schemas accepted by their
deployed provider runtimes
**So that** agentic inventory can reach model inference instead of failing before perception begins

## Acceptance Criteria

- [x] Stagehand inventory scope and detail schemas remain strict and typed while avoiding nullable
  or union-typed parameters in the provider-compiled schema.
- [x] The Anthropic computer-use tool schema uses only JSON Schema keywords accepted by the active
  computer-use endpoint; BookSaver continues to enforce collection bounds after decoding.
- [x] Provider-schema incompatibility is classified into a bounded content-free diagnostic category
  without persisting prompts, page content, screenshots, raw provider messages, or session material.
- [x] Regression tests reproduce the live Stagehand union-limit rejection and Anthropic unsupported
  `maxItems` rejection without making live provider calls.
- [x] Extraction and fallback retain the same typed evidence, positive-only reconciliation, action,
  destination, session, deadline, and cost boundaries.
- [x] A cookie-free exact-image smoke proves Stagehand and Anthropic accept the repaired schemas
  before production deployment.

## Dependencies

- US-153, US-156, US-157; ADR-036, ADR-037, ADR-039, and ADR-040.

## Out of Scope

- Weakening domain validation, increasing provider budgets, changing models, accepting arbitrary
  tool output, or changing Booking.com navigation and reconciliation policy.
