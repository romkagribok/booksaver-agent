---
id: 006-search-journey-monitor
unit: 001-search-journey-monitor
intent: 002-agentic-search-monitor
type: ddd-construction-bolt
status: planned
stories:
  - 001-capture-occupancy-at-registration
  - 002-run-scripted-search-journey
  - 003-extract-equivalent-offer-total
created: 2026-07-05T23:10:00Z
started: null
completed: null
current_stage: null
stages_completed: []
requires_bolts:
  - 001-core-local-data
  - 002-core-local-data
  - 003-booking-com-price-monitor
  - 004-savings-detection-notifications
enables_bolts:
  - 007-agentic-escalation
requires_units: []
blocks: false
complexity:
  avg_complexity: 4
  avg_uncertainty: 4
  max_dependencies: 4
  testing_scope: 4
---

# Bolt: 006-search-journey-monitor

## Overview

First bolt of intent 002. Replaces the manage-page price check with a scripted full search journey
that discovers the real bookable total for an equivalent refundable room and feeds it into the
existing savings pipeline. Adds the required `Occupancy` value object to registration with a
migration path (no silent defaults). The manage page stops being a price source (kept only for
session validation).

## Objective

On each scheduled tick: restore the saved session, run the full Booking.com search journey
(search box → results → verified property page → room table) using the booking's property name,
exact dates, and real occupancy; extract equivalent refundable candidates with all-in totals;
emit the cheapest as a success `CheckResult`; fail with distinct codes otherwise. Downstream
savings/notification/rebook interfaces and tests remain untouched.

## Stories Included

- **US-017**: Capture occupancy at registration (Must)
- **US-018**: Run scripted search journey to verified property page (Must)
- **US-019**: Extract equivalent offer total and feed savings pipeline (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ⬜ **1. Domain Model**: `Occupancy` VO, journey-step model (named steps + outcomes), offer-candidate
  and equivalence-judgment concepts, new failure codes (`OCCUPANCY_MISSING`, `PROPERTY_NOT_FOUND`,
  `NO_EQUIVALENT_OFFER`, `BOT_WALL`)
- ⬜ **2. Technical Design**: journey orchestrator in monitor layer; browser-port extensions;
  DOM-first extraction with LLM judgment calls; migration plan for `bookings` table
- ⬜ **3. ADR Analysis**: search-journey-replaces-manage-page (price source); occupancy-required
  (no default); step-decomposition designed for Unit-2 escalation points
- ⬜ **4. Implement**
- ⬜ **5. Test**: journey step machine with fake browser pages; extraction/equivalence exclusion
  rules; migration + occupancy-missing behavior; savings pipeline regression (existing 211 tests pass)

## Dependencies

### Requires
- Bolts 001–002 (Booking aggregate, registration, SQLite, scheduler)
- Bolt 003 (browser port, session manager, failure tracker, CheckResult, LLM adapter)
- Bolt 004 (savings pipeline consuming CheckResult — regression surface)

### Enables
- Bolt 007 (agentic escalation wraps this bolt's journey steps)

## Success Criteria

- [ ] Registration requires occupancy; migrated bookings fail checks with `OCCUPANCY_MISSING` until
      backfilled via CLI
- [ ] Full search journey completes against verified property with exact dates + occupancy
- [ ] Cheapest equivalent refundable all-in total emitted as CheckResult; below-confidence matches
      excluded, never guessed into savings
- [ ] Manage page no longer opened for prices
- [ ] All pre-existing tests still pass; new failure codes visible in check history

## Notes

- LLM usage in this bolt is judgment-only (room-type match, refundability wording) — target ≤ 2 calls
  on the scripted happy path. The browser-agent loop is bolt 007.
- Journey steps must be individually named and reportable — bolt 007 attaches escalation at exactly
  those seams.
