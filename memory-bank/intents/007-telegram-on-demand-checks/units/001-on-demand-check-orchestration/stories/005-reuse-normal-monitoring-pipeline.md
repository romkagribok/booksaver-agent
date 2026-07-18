---
id: 005-reuse-normal-monitoring-pipeline
unit: 001-on-demand-check-orchestration
intent: 007-telegram-on-demand-checks
status: complete
priority: must
created: 2026-07-18T23:40:00Z
assigned_bolt: 019-on-demand-check-orchestration
implemented: true
---

# Story: Reuse the Normal Monitoring Pipeline

**Global story ID**: US-056

## User Story

**As a** BookSaver user
**I want** an immediate check to behave like a scheduled check
**So that** it records evidence and alerts me when it finds real savings

## Acceptance Criteria

- [x] Immediate checks use normal session, monitor, action guard, timeout, trace, history, and failure tracking.
- [x] Results enter the normal savings pipeline and owner notifier resolver.
- [x] Savings produce the existing proactive alert plus the immediate completion response.
- [x] Personal-key failures use the existing best-effort owner notification.

## Dependencies

- US-019 savings pipeline; US-022 traces; US-030 owner alert routing; US-035 session modes.
