---
id: 002-govern-canary-promotion-and-regression-rollback
unit: 003-agentic-browser-qualification
intent: 023-replaceable-agentic-browser-executor
status: in-progress
priority: must
created: 2026-08-16T19:18:41Z
assigned_bolt: 052-agentic-browser-qualification
implemented: false
---

# Story: Govern Canary Promotion and Regression Rollback

## User Story

**As a** deployment owner
**I want** an auditable threshold evaluator and fail-closed rollback policy
**So that** invited users receive agentic checks only after real safety/reliability evidence

## Acceptance Criteria

- [x] The ledger stores only timestamps, closed outcomes, costs, latency, fallback, eligibility, and
  manual comparison verdicts.
- [x] Promotion requires 30 checks over 14 days, 10 correct manual comparisons, 95% valid eligible
  observations, average cost <= USD 0.10, p95 cost <= USD 0.50, p95 duration <= 180 seconds,
  fallback <= 20%, and zero critical violations/cap breaches.
- [x] Threshold failure cannot promote; a safety/privacy/price regression or three consecutive
  eligible invalid observations during the rollback window returns routing to legacy.
- [x] Promotion remains an explicit owner action; tests cannot fabricate its live evidence.

## Dependencies

- US-151 and owner-operated live canary.

## Out of Scope

- Automated invited-user promotion or production canary execution in tests.
