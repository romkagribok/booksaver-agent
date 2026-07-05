---
unit: 002-booking-com-price-monitor
bolt: 003-booking-com-price-monitor
id: ADR-008
title: Synchronous Playwright API in the scheduler loop
status: accepted
updated: 2026-07-05T00:00:00Z
---

# ADR-008: Synchronous Playwright API

## Context

Playwright ships both `sync_api` and `async_api`. The daemon's scheduler (ADR-006) is a
synchronous `threading.Event` loop on the main thread; checks run sequentially per tick.

## Decision

Use **`playwright.sync_api`** throughout the browser adapter.

## Rationale

- The scheduler loop is synchronous by design; one booking is checked at a time. Async
  buys concurrency we do not need for a handful of bookings and would force an event loop
  into the daemon (`asyncio.run` per tick or a full async rewrite of Bolt 002).
- Sync code is simpler to test and reason about; failure handling per US-014 stays
  straight-line try/except.
- The `BrowserSession` port hides the choice: if a future unit needs concurrent checks,
  the adapter can switch to async behind the same interface.

## Consequences

- Checks are sequential; a tick's duration grows linearly with booking count. Fine for the
  personal-tool scale (a handful of active bookings).
- No `asyncio` anywhere in the codebase yet — keeps Bolt 002's threading model untouched.
