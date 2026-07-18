---
id: 003-serialize-all-check-work
unit: 001-on-demand-check-orchestration
intent: 007-telegram-on-demand-checks
status: complete
priority: must
created: 2026-07-18T23:40:00Z
assigned_bolt: 019-on-demand-check-orchestration
implemented: true
---

# Story: Serialize All Check Work

**Global story ID**: US-054

## User Story

**As an** operator
**I want** scheduled and manual checks coordinated by one runtime service
**So that** they cannot launch competing browsers or duplicate a booking check

## Acceptance Criteria

- [x] One non-blocking gate serializes all scheduled/manual browser work.
- [x] Busy manual requests are rejected rather than queued; busy scheduled ticks skip cleanly.
- [x] One shared execution method owns browser, monitor, persistence, savings, and notification work.
- [x] The scheduler job and Telegram gateway receive the same daemon-lifetime coordinator.

## Dependencies

- US-005 scheduled browser checks; US-031 fair scheduling.
