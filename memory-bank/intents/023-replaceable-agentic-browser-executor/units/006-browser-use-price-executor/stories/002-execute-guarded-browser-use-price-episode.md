---
id: 002-execute-guarded-browser-use-price-episode
unit: 006-browser-use-price-executor
intent: 023-replaceable-agentic-browser-executor
status: draft
priority: must
created: 2026-09-02T23:44:45Z
assigned_bolt: 064-browser-use-price-executor
implemented: false
---

# Story: Execute a Guarded Typed Browser Use Price Episode

## User Story

**As a** BookSaver user
**I want** an agent to navigate the current Booking.com price experience like a human within strict
read-only boundaries
**So that** BookSaver can obtain current offers without trusting exact DOM structure or model
conclusions

## Acceptance Criteria

- [ ] The agent runs locally in a fresh mobile Chromium with an opaque owner-bound session lease and
  no Browser Use Cloud dependency.
- [ ] Stock actions are removed and every allowed physical action, destination, and typed value is
  validated before and after execution.
- [ ] Only exact trusted query values may be typed; credentials, authentication, challenges, files,
  shell, clipboard, transactions, arbitrary URLs, and popups are unavailable.
- [ ] Typed output maps to the existing price observation contract and the existing BookSaver
  validator remains authoritative for every required fact and offer.
- [ ] Actions, model calls, tokens, cost, latency, deadline, and cleanup are exact on success and all
  terminal failures.

## Dependencies

- US-164; ADR-036, ADR-037, ADR-040, and ADR-041.
