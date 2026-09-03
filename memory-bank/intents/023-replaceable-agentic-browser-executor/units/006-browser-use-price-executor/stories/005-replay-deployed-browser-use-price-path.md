---
id: 005-replay-deployed-browser-use-price-path
unit: 006-browser-use-price-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-09-02T23:44:45Z
assigned_bolt: 064-browser-use-price-executor
implemented: true
---

# Story: Replay the Deployed Browser Use Price Path Without Telegram

## User Story

**As a** BookSaver operator
**I want** a safe command that waits for the deployed price executor to finish
**So that** production failures can be diagnosed and corrected without asking a user to repeatedly
trigger Telegram

## Acceptance Criteria

- [x] Replay uses the deployed image, real price-executor factory, owner-authorized encrypted
  session, and an isolated state copy under the coordinator/browser lease.
- [x] Notifications and authoritative production booking mutations are disabled.
- [x] The command waits for terminal completion and exits zero only when BookSaver accepts a complete
  Browser Use price observation.
- [x] Routing tests prove manual and scheduled jobs use the same Browser Use adapter.
- [x] Exact-container and VPS evidence records terminal status, accepted/rejected offer counts,
  action/model usage, cost, and duration without content-bearing artifacts.

## Dependencies

- US-164 through US-167.
