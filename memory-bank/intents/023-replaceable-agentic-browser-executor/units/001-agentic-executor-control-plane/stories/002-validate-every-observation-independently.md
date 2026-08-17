---
id: 002-validate-every-observation-independently
unit: 001-agentic-executor-control-plane
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: '2026-08-16T19:18:41Z'
assigned_bolt: 050-agentic-executor-control-plane
implemented: true
---

# Story: Validate Every Observation Independently

## User Story

**As a** BookSaver user
**I want** agent observations independently qualified by BookSaver
**So that** DOM or model mistakes cannot produce a false savings alert

## Acceptance Criteria

- [x] Property, dates, occupancy, authentication, currency, all-in status, and refundability must be
  explicit and consistent with the trusted request.
- [x] Missing/conflicting evidence fails closed with a typed rejection.
- [x] Room equivalence and cheapest-offer selection reuse BookSaver-owned policy only.
- [x] An executor cannot directly create persistence transitions or notifications.

## Dependencies

- US-143 and existing offer/equivalence policy.

## Out of Scope

- Improving semantic room equivalence policy.
