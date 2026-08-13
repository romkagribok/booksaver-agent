---
id: 002-notify-owner-of-maintenance-required
unit: 003-dom-drift-incident-operations
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-13T01:59:59.000Z
assigned_bolt: 044-dom-drift-incident-operations
implemented: true
---

# Story: Notify Owner of Maintenance Required

## User Story

**As a** BookSaver owner
**I want** a concise Telegram alert when DOM drift needs maintenance
**So that** I can inspect and patch the affected step before adaptive recovery stops succeeding

## Acceptance Criteria

- [ ] **Given** an incident requests notification, **When** Telegram delivery is built, **Then** it is
  addressed only to the configured owner chat and includes incident ID, journey/step, safe category,
  recovered state, occurrence count, ordered model roles, budget/provider state, and local command.
- [ ] **Given** any incident source contains private data, **When** message validation runs, **Then**
  no user/reservation/property/stay/URL/query/page/screenshot/prompt/response/cookie/token/key value is
  permitted in the payload or ordinary delivery log.
- [ ] **Given** the same fingerprint repeats, **When** no severity/category change occurs, **Then** no
  more than one Telegram alert is sent within six hours.
- [ ] **Given** Telegram delivery fails, **When** bounded retry runs through the existing daemon
  lifecycle, **Then** delivery state persists and browser cleanup/caller response are unaffected.
- [ ] **Given** diagnostic encryption/storage fails, **When** notification is due, **Then** the
  content-free alert is still sent with explicit `evidence_unavailable` status.
- [ ] **Given** the affected caller receives their browser result, **When** the owner alert is sent,
  **Then** caller-facing output remains caller-safe and does not reveal admin diagnostics.

## Technical Notes

- Reuse configured owner identity and Telegram sender; do not add a new bot/process.
- Validate the final payload against an explicit field allowlist.
- Surface pending/failed alert count safely through `/status` and CLI.

## Dependencies

### Requires

- US-137 and existing owner-scoped Telegram infrastructure.

### Enables

- Human maintenance response before LLM recovery degrades further.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Owner chat ID missing | Persist explicit notification-config failure and show in `/status` |
| Telegram outage lasts beyond retry window | Retain failed state for later safe operator inspection |
| Severity increases during suppression window | Send one updated alert |

## Out of Scope

- Sending incident evidence to an invited user or external operations service.
- Automatically acknowledging or resolving incidents from Telegram.
