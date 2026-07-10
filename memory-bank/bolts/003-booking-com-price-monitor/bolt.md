---
id: 003-booking-com-price-monitor
unit: 002-booking-com-price-monitor
intent: 001-booksaver-agent-mvp
type: ddd-construction-bolt
status: complete
stories:
  - 001-store-booking-com-session-locally
  - 002-run-scheduled-browser-check
  - 003-extract-booking-and-offer-data-with-llm
  - 004-handle-check-failures-gracefully
created: 2026-07-05T00:00:00.000Z
started: 2026-07-05T00:00:00.000Z
completed: "2026-07-05T18:39:02Z"
current_stage: null
stages_completed:
  - name: model
    completed: 2026-07-05T00:00:00.000Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-05T00:00:00.000Z
    artifact: ddd-02-technical-design.md
  - name: adr
    completed: 2026-07-05T00:00:00.000Z
    artifact: adr-007-playwright-browser-automation.md, adr-008-sync-playwright-api.md, adr-009-anthropic-sdk-llm-extraction.md, adr-010-json-session-file.md
  - name: implement
    completed: 2026-07-05T00:00:00.000Z
    artifact: src/booksaver/monitor/ + domain/check_result.py + domain/session.py + infrastructure adapters
  - name: test
    completed: 2026-07-05T00:00:00.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 001-core-local-data
  - 002-core-local-data
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 3
  max_dependencies: 3
  testing_scope: 3
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

- ✅ **1. Domain Model**: Complete → ddd-01-domain-model.md
- ✅ **2. Technical Design**: Complete → ddd-02-technical-design.md
- ✅ **3. ADR Analysis**: Complete → adr-007 through adr-010
- ✅ **4. Implement**: Complete → src/booksaver/monitor/ + adapters
- ✅ **5. Test**: Complete → ddd-03-test-report.md (136/136)

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
