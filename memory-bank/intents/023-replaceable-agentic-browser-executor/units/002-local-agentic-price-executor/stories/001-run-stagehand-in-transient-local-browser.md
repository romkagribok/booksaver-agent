---
id: 001-run-stagehand-in-transient-local-browser
unit: 002-local-agentic-price-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: '2026-08-16T19:18:41Z'
assigned_bolt: 051-local-agentic-price-executor
implemented: true
---

# Story: Run Stagehand in a Transient Local Browser

## User Story

**As a** self-hosting owner
**I want** Stagehand to run locally against the installed Chromium
**So that** browser/session custody remains on my host without a managed service

## Acceptance Criteria

- [x] Stagehand 4.0.1 is exactly pinned and invoked through a dedicated async runner.
- [x] The adapter uses the existing Chromium executable and global browser lease.
- [x] A fresh profile receives cookies locally and is destroyed on success/failure/cancellation.
- [x] Computer use can continue on the same browser connection after semantic failure.

## Dependencies

- Unit 001 session lease and executor contract.

## Out of Scope

- Sidecars, Browserbase, Browser Use Cloud, or persistent profiles.
