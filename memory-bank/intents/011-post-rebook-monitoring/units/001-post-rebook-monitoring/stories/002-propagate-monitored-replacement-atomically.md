---
id: 002-propagate-monitored-replacement-atomically
unit: 001-post-rebook-monitoring
intent: 011-post-rebook-monitoring
status: complete
priority: must
created: 2026-07-19T19:50:29.000Z
assigned_bolt: 023-post-rebook-monitoring
implemented: true
---

# Story: Propagate Monitored Replacement Atomically

**Global story ID**: US-073

## User Story

**As a** BookSaver user
**I want** my successfully rebooked reservation to replace the monitored baseline
**So that** future checks continue saving from the amount I actually paid

## Acceptance Criteria

- [ ] Active access, ownership, completed session linkage, source snapshot, and uniqueness are checked in one transaction.
- [ ] Stable booking identity/history remains while confirmation/reference/baseline/status update.
- [ ] Stale, conflicting, revoked, foreign, missing, or concurrently changed state rolls back fully.
- [ ] Scheduler and immediate checks read the replacement immediately after commit.

## Dependencies

- US-072 actual replacement facts.
