---
id: 004-share-daily-check-and-llm-budgets
unit: 001-on-demand-check-orchestration
intent: 007-telegram-on-demand-checks
status: complete
priority: must
created: 2026-07-18T23:40:00Z
assigned_bolt: 019-on-demand-check-orchestration
implemented: true
---

# Story: Share Daily Check and LLM Budgets

**Global story ID**: US-055

## User Story

**As an** operator
**I want** both check entry points to consume the same user budgets
**So that** manual checking cannot bypass cost and fairness controls

## Acceptance Criteria

- [x] Daily counters are thread-safe and shared across scheduled/manual work.
- [x] A scheduled plan never includes more bookings than a user's remaining check quota.
- [x] Manual checks refuse at the shared check cap and consume one allowance only when execution starts.
- [x] Actual LLM calls are counted; per-check settings are capped to remaining daily calls.
- [x] Zero remaining LLM calls causes DOM/scripted-only execution, not a skipped real check.

## Dependencies

- US-021 hard per-check budgets; US-027 key resolution; US-031 per-user limits.
