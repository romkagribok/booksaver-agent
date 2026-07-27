---
id: 002-reject-superseded-rebook-selection
unit: 001-current-rebook-opportunities
intent: 017-current-rebook-opportunities
status: complete
priority: must
created: 2026-07-27T02:10:44.000Z
assigned_bolt: 032-current-rebook-opportunities
implemented: true
---

# Story: Reject Superseded Rebook Selection

**Global story ID**: US-107

## User Story

**As a** user returning to an older Telegram picker
**I want** BookSaver to reject a replaced price choice
**So that** I do not begin cancelling a reservation for stale savings.

## Acceptance Criteria

- [x] A stale callback is acknowledged but starts no session or confirmation.
- [x] `/rebook <old-id>` returns current-picker guidance.
- [x] The application service repeats the guard before session creation.
- [x] The current ID still starts the existing guarded flow.
- [x] A freshness race creates no partial session or navigation.

## Dependencies

US-106 current opportunity selection.
