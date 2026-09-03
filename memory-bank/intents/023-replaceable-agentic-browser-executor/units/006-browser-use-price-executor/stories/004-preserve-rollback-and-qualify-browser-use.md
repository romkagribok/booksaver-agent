---
id: 004-preserve-rollback-and-qualify-browser-use
unit: 006-browser-use-price-executor
intent: 023-replaceable-agentic-browser-executor
status: draft
priority: must
created: 2026-09-02T23:44:45Z
assigned_bolt: 064-browser-use-price-executor
implemented: false
---

# Story: Preserve Explicit Rollback and Qualify Browser Use Independently

## User Story

**As a** BookSaver deployment owner
**I want** Browser Use evidence and rollback choices to remain explicit
**So that** failures are visible, Stagehand can be evaluated later, and old evidence cannot silently
promote a new executor

## Acceptance Criteria

- [ ] Executor selection defaults to Browser Use and allows explicit Stagehand selection for future
  jobs without changing domain code or booking data.
- [ ] Browser Use failure is terminal for the current job and cannot cascade to Stagehand or legacy
  execution.
- [ ] Browser Use canary evidence uses a distinct policy identity from Stagehand evidence.
- [ ] Owner canary applies the USD 0.25 average threshold; invited-user promotion additionally
  requires USD 0.10 average while all safety, correctness, p95, and hard-cap gates remain binding.
- [ ] The deterministic path remains available until its separately approved retirement window.

## Dependencies

- US-152, US-164, and US-165.
