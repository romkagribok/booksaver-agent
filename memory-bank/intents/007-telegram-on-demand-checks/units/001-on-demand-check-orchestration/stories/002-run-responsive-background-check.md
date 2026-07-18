---
id: 002-run-responsive-background-check
unit: 001-on-demand-check-orchestration
intent: 007-telegram-on-demand-checks
status: complete
priority: must
created: 2026-07-18T23:40:00Z
assigned_bolt: 019-on-demand-check-orchestration
implemented: true
---

# Story: Run a Responsive Background Check

**Global story ID**: US-053

## User Story

**As an** authorized Telegram user
**I want** an immediate check to run without freezing the bot
**So that** I can continue using Telegram and receive a clear result afterward

## Acceptance Criteria

- [x] Command/callback handling acknowledges before browser navigation.
- [x] A background worker re-resolves active user, ownership, and booking state.
- [x] Completion reports concise success or persisted failure details and check ID.
- [x] Shutdown refuses new work and workers are daemonized/stop-aware.

## Dependencies

- US-023 daemon Telegram loop; US-036 check result presentation.
