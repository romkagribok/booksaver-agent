---
unit: 001-production-reliability
intent: 004-production-hardening
phase: inception
status: complete
unit_type: cli
default_bolt_type: simple-construction-bolt
created: 2026-07-18T17:48:48.000Z
updated: 2026-07-18T21:47:06Z
---

# Unit Brief: Production Reliability

## Purpose

Turn the first real VPS check failures into bounded, safe, deployable behavior while keeping the LLM
as the adaptive layer for Booking.com layout changes and preserving every existing safety invariant.

## Scope

### In Scope

- Detect and refuse repeated successful-but-unverified browser-agent actions early.
- Give the LLM a fresh screenshot and explicit feedback when a duplicate is refused.
- Continue only a bounded `fill_search` give-up/budget failure from trusted booking data.
- Include `schema.sql` in built Python distributions.
- Complete Telegram command discovery and resolve unique caller-owned booking prefixes.
- Add regression tests and record wheel/static/test evidence.
- Enter Booking.com searches through the persisted trusted query without homepage form interaction.
- Preserve guarded LLM adaptation for results, property, room-view, and extraction drift.
- Preserve full context on the fresh property href, dismiss consent, and interpret availability/rate
  readiness without requiring one legacy selector.

### Out of Scope

- Calendar-layout-specific scraping as the only recovery mechanism.
- Changes to property, date, room, refundability, or occupancy equivalence rules.
- New Booking.com providers, residential proxies, or autonomous rebooking.
- New database schema versions, runtime dependencies, bot commands, or deployment platforms.
- A live Booking.com production check from the developer environment.

---

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Screenshot-aware recovery adapts instead of repeatedly executing one action | Must |
| FR-2 | `fill_search` can continue safely from persisted exact booking data | Must |
| FR-3 | Installed distributions include the SQLite schema resource | Must |
| FR-4 | Telegram command discovery and accepted booking identifiers are consistent | Must |
| FR-5 | Enter live searches through the trusted Booking.com results query | Must |
| FR-6 | Interpret the property availability page without selector lock-in | Must |

---

## Domain Concepts

### Key Entities and Value Objects

| Concept | Description | Relevant attributes |
|---------|-------------|---------------------|
| Agent action proposal | LLM-requested browser operation before adapter execution | action name, arguments, observation tier, repetition count |
| Journey recovery outcome | Bounded result of LLM takeover for one named step | step, success, failure code, detail |
| Trusted search context | Persisted values authoritative for a price check | property, check-in/out, adults, children, rooms |
| Booking identifier | Full UUID or user-visible prefix used by Telegram | value, caller scope, uniqueness |
| Distribution resource | Non-Python file required by installed runtime | wheel path, expected package path |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| Detect repeated proposal | Determines whether the next identical action may execute | normalized proposal history | execute/refuse decision + trace |
| Continue trusted search | Navigates from an exhausted `fill_search` recovery without agent-authored parameters | persisted booking | exact search URL, then verified page |
| Resolve booking reference | Finds only an exact or unique caller-owned booking | caller user ID, reference | booking or non-disclosing not-found |
| Verify wheel contents | Confirms required persistence resource is shipped | built wheel | pass/fail evidence |

---

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 6 |
| Must Have | 6 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-037 | Adapt after repeated browser actions | Must | Complete |
| US-038 | Continue `fill_search` from trusted booking data | Must | Complete |
| US-039 | Package the persistence schema | Must | Complete |
| US-040 | Discover commands and use displayed booking identifiers | Must | Complete |
| US-041 | Enter search from trusted query | Must | Complete |
| US-042 | Handle property availability page | Must | Complete |

---

## Dependencies

### Depends On

| Capability | Reason |
|------------|--------|
| Intent 002 / bolt 006 | Existing exact search URL and downstream property/context verification |
| Intent 002 / bolt 007 | Screenshot-aware `BrowserAgent`, action guard, caps, and traces |
| Intent 003 / bolts 008–010 | Telegram gateway, user-scoped repositories, and command handlers |
| Intent 003 / bolt 012 | Installed-wheel Docker/VPS deployment shape |

### Depended By

| Consumer | Reason |
|----------|--------|
| VPS operations | Requires the reviewed code to be built, deployed, and smoke-tested |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| Booking.com | Live price-check pages and changing layouts | High |
| Anthropic API | Screenshot-aware recovery decisions | Medium |
| Telegram Bot API | User command surface | Low |

---

## Technical Context

### Suggested Technology

Use existing Python 3.11+, synchronous Playwright, Anthropic tool-use loop, SQLite repositories,
stdlib Telegram transport, setuptools wheel configuration, pytest, Ruff, and mypy. Add no dependency.

### Integration Points

| Integration | Type | Protocol |
|-------------|------|----------|
| `BrowserAgent` → guarded adapter | In-process port | Typed Python calls |
| `SearchJourney` → Booking.com | Browser | HTTPS through Playwright |
| Telegram handlers → booking repository | In-process port | User-scoped Python calls |
| Installed package → schema resource | Package data | Filesystem/resource path |

### Data Storage

| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| Bookings, checks, traces | SQLite | Small, owner-operated | Existing policy |
| Failure screenshots | Local files | Bounded/rotated | Existing policy |
| Schema resource | Wheel package data | One static SQL file | Distribution lifetime |

---

## Constraints

- Existing action guard and budget failures remain authoritative.
- Only persisted booking data may construct the safe continuation URL.
- Explicit unavailable inventory and bot walls cannot satisfy rate readiness.
- Prefix lookup must never search outside the caller's repository scope.
- Installed runtime must not depend on a source-tree-relative schema path.
- The existing safety and equivalence regression surfaces are frozen.

---

## Success Criteria

### Functional

- [x] Duplicate identical agent execution is contained and a fresh visual observation is provided.
- [x] `fill_search` can safely continue only for the two approved bounded failure codes.
- [x] Fresh wheel installations contain and can load `schema.sql`.
- [x] Telegram exposes the complete command reference and accepts unique user-owned short IDs.
- [x] Trusted results navigation replaces homepage form interaction.
- [x] Property navigation, complete context verification, and semantic rate readiness are distinct.

### Non-Functional

- [x] No destructive action or downstream verification bypass is introduced.
- [x] Full pytest suite, Ruff, mypy, and wheel-content checks pass.

### Quality

- [x] All acceptance criteria have automated coverage where practical.
- [x] AI-DLC artifacts and the global story index remain consistent through the US-042 correction.
- [x] Code and documentation are reviewed and approved before commit/push.

---

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| `013-production-reliability` | Simple Construction | US-037–US-040 | Deliver and verify the cohesive production-hardening slice |
| `014-production-reliability` | Simple Construction | US-041 | Promote trusted results navigation to primary search entry and preserve downstream LLM recovery |
| `015-production-reliability` | Simple Construction | US-042 | Preserve property context, dismiss consent, and interpret rate availability semantically |

## Notes

Implementation and tests were started before this intent was recorded. Construction artifacts must
preserve that chronology as a process deviation rather than implying the plan preceded the code.
