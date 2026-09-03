---
id: 001-default-price-checks-to-browser-use
unit: 006-browser-use-price-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-09-02T23:44:45Z
assigned_bolt: 064-browser-use-price-executor
implemented: true
---

# Story: Default Manual and Scheduled Price Checks to Browser Use

## User Story

**As a** BookSaver deployment owner
**I want** both immediate and scheduled price checks to use the same Browser Use executor
**So that** ordinary Booking.com DOM churn no longer requires separate selector maintenance across
price-check triggers

## Acceptance Criteria

- [x] Owner-canary `/checknow` and scheduled price routes construct the same Browser Use-backed
  `PriceBrowserExecutor`.
- [x] The trigger does not change validation, budgeting, deadlines, session ownership, persistence,
  savings evaluation, or notification policy.
- [x] Invited-user execution retains disclosure and qualification admission.
- [x] The current-run inventory prerequisite also uses Browser Use; `/connect` remains unchanged.

## Dependencies

- US-143 through US-146 and US-160 through US-163.
