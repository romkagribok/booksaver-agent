---
id: 003-booking-com-price-monitor
unit: 002-booking-com-price-monitor
intent: 001-booksaver-agent-mvp
type: ddd-construction-bolt
status: in-progress
stories:
  - 001-store-booking-com-session-locally
  - 002-run-scheduled-browser-check
  - 003-extract-booking-and-offer-data-with-llm
  - 004-handle-check-failures-gracefully
created: 2026-07-05T00:00:00Z
started: 2026-07-05T00:00:00Z
completed: null
current_stage: model
stages_completed: []

# Bolt Dependencies
requires_bolts:
  - 001-core-local-data
  - 002-core-local-data
enables_bolts: []
requires_units: []
blocks: false

# Complexity Assessment
complexity:
  avg_complexity: 3        # browser automation + LLM + external site = high
  avg_uncertainty: 3       # Booking.com DOM changes, session handling, LLM extraction
  max_dependencies: 3      # needs Config, Booking, Scheduler, LocalStore from Unit 1
  testing_scope: 3         # integration with real browser + mock LLM responses
---

# Bolt: 003-booking-com-price-monitor

## Overview

Implements the browser automation and LLM extraction core of BookSaver Agent.
Introduces the first real external dependencies: Playwright for browser automation
and the Anthropic API (or compatible) for LLM-assisted page interpretation. Builds
on Unit 1's Config, Booking records, Scheduler hook, and LocalStore.

## Objective

On each scheduled tick: open the user's Booking.com booking in a browser the daemon
controls, navigate to the manage-booking flow, extract the current live price via DOM
selectors (falling back to LLM), record a CheckResult in local storage, and handle
failures without losing the booking or crashing the daemon.

## Stories Included

- **US-004**: Store Booking.com session locally (Must)
- **US-005**: Run scheduled browser check (Must)
- **US-006**: Extract booking and offer data with LLM (Must)
- **US-014**: Handle check failures gracefully (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [ ] **1. Domain Model**: Pending → ddd-01-domain-model.md
- [ ] **2. Technical Design**: Pending → ddd-02-technical-design.md
- [ ] **3. ADR Analysis**: Pending → adr-*.md
- [ ] **4. Implement**: Pending → src/
- [ ] **5. Test**: Pending → ddd-03-test-report.md

## Dependencies

### Requires
- Bolt 001 (Config, DataDirectory, Booking aggregates, BookingRepository)
- Bolt 002 (Scheduler.register() hook, daemon running context)

### Enables
- Unit 3 (003-savings-detection-notifications) consumes CheckResult records

## Success Criteria

- [ ] Booking.com session authenticated via browser and cookies persisted locally
- [ ] On each scheduler tick, daemon navigates to each active booking's manage page
- [ ] CheckResult (price, currency, refund indicators, extracted fields) stored in local DB
- [ ] LLM extraction invoked when DOM selectors are insufficient
- [ ] Failures logged; booking never removed due to check failure
- [ ] Repeated failures optionally surface a local warning

## Notes

- This bolt introduces the first third-party runtime dependencies (Playwright, Anthropic SDK).
  Choices must be captured as ADRs in Stage 3.
- Session cookies stored locally only — never sent to any BookSaver backend (US-013).
- `check_history` table (stub from Bolt 001 schema) gets its columns finalized here.
