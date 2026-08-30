---
id: 006-execute-bookings-inventory-with-browser-use
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-08-30T18:00:44.000Z
assigned_bolt: 060-agentic-inventory-executor
implemented: true
---

# Story: Execute `/bookings` Inventory with Browser Use

## User Story

**As a** BookSaver user
**I want** `/bookings` to use a mature local browser agent that can inspect the current Booking.com
experience without exact selectors or read-only route names
**So that** inventory refresh is reliable under ordinary presentation churn while BookSaver keeps
all safety, privacy, validation, and persistence authority

## Acceptance Criteria

- [x] Only `SynchronizationTrigger.BOOKINGS` selects a pinned established Browser Use OSS agent;
  post-connect, `/checknow`, scheduled inventory, and price execution retain their current paths.
- [x] Browser Use runs locally in a fresh transient Chromium with the owner-bound session lease,
  configured mobile identity, existing Anthropic key, and no Browser Use Cloud dependency.
- [x] Browser Use receives only guarded read-only click, scroll, safe-key, wait, typed observation,
  and typed terminal tools, with one action per step and existing action/cost/deadline caps.
- [x] The deny-oriented action guard rejects authentication, challenge solving, typing, arbitrary
  navigation, tabs/popups, file/shell/clipboard tools, account modification, cancellation,
  reservation, checkout, purchase, payment, external destinations, and unsafe post-action routes.
- [x] The adapter returns the existing provider-neutral inventory result. BookSaver validates every
  positive fact, preserves unseen/cached rows, and alone proves refreshed authentication.
- [x] Browser Use failure preserves last-safe inventory and does not run Stagehand or legacy
  inventory in the same `/bookings` job.
- [x] Telemetry, cloud sync/version checks, exported history, GIF/video, HAR, trace, and screenshot
  persistence are disabled before import and absent after execution.
- [x] Contract, coordinator-routing, privacy, safety, dependency, exact-container, egress, and
  teardown tests pass without weakening existing Stagehand or price coverage.

## Dependencies

- US-153 and US-156 through US-159; ADR-036 through ADR-040.

## Out of Scope

- Browser Use for post-connect, `/checknow`, scheduler, `/connect`, or price checks; Browser Use
  Cloud; new provider secrets; absence reconciliation; transaction actions; Stagehand removal.
