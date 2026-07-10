---
id: 006-search-journey-monitor
unit: 001-search-journey-monitor
intent: 002-agentic-search-monitor
type: ddd-construction-bolt
status: complete
stories:
  - 001-capture-occupancy-at-registration
  - 002-run-scripted-search-journey
  - 003-extract-equivalent-offer-total
created: 2026-07-05T23:10:00.000Z
started: 2026-07-05T23:25:00.000Z
completed: "2026-07-05T23:25:58Z"
current_stage: null
stages_completed:
  - name: model
    completed: 2026-07-05T23:30:00.000Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-05T23:35:00.000Z
    artifact: ddd-02-technical-design.md
  - name: adr
    completed: 2026-07-05T23:40:00.000Z
    artifact: adr-013-search-journey-price-source.md, adr-014-occupancy-required-no-default.md
  - name: implement
    completed: 2026-07-06T00:00:00.000Z
    artifact: src/booksaver/monitor/{search_journey,search_check_job,room_table}.py + domain/{journey,offer}.py + occupancy across domain/persistence/CLI
  - name: test
    completed: 2026-07-06T00:05:00.000Z
    artifact: ddd-03-test-report.md
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

- ✅ **1. Domain Model**: Complete → ddd-01-domain-model.md
- ✅ **2. Technical Design**: Complete → ddd-02-technical-design.md
- ✅ **3. ADR Analysis**: Complete → adr-013, adr-014
- ✅ **4. Implement**: Complete → search journey + occupancy + offer selection + daemon rewire
- ✅ **5. Test**: Complete → ddd-03-test-report.md (277/277; 66 new)

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
