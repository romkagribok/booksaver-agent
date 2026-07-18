---
stage: implement
bolt: 014-production-reliability
created: 2026-07-18T19:19:28Z
---

## Implementation Walkthrough: Production Reliability

### Summary

BookSaver now begins live-price checks with the trusted Booking.com search-results query and no longer
operates the homepage form. The verified results-to-property-to-room-table journey, fail-closed safety
rules, and guarded downstream LLM recovery remain in place.

### Structure Overview

The existing search journey remains the sole navigation coordinator. Its active sequence is smaller,
while the result selection, property navigation, context verification, room-view handling, agent
budget, action guard, extraction, equivalence, and savings boundaries remain unchanged.

### Completed Work

- [x] `src/booksaver/monitor/search_journey.py` - Enters through trusted results navigation, removes
  active homepage/form automation and its late fallback, retains downstream scripted and LLM seams,
  and detects bot walls on the results page.
- [x] `tests/unit/monitor/test_search_journey.py` - Verifies active step order, exact first navigation,
  absence of form operations, property/context failures, and wall/auth classification.
- [x] `tests/unit/monitor/test_search_journey_query.py` - Verifies persisted query values, encoding,
  occupancy, and optional destination identity.
- [x] `tests/unit/monitor/test_journey_escalation.py` - Verifies guarded LLM recovery remains available
  on results-layout drift and budget/give-up/bot-wall outcomes remain terminal.
- [x] `memory-bank/bolts/014-production-reliability/adr-020-query-driven-search-entry.md` - Records the
  deliberate amendment to ADR-013's homepage entry sequence.
- [x] `memory-bank/standards/decision-index.md` - Makes the amended price-journey decision discoverable.
- [x] `memory-bank/standards/system-architecture.md` - Aligns the architecture boundary with trusted
  results entry and downstream LLM recovery.

### Key Decisions

- **Search query, not property deep link**: Booking.com still produces fresh result cards and the
  property href used for price discovery.
- **Remove rather than time-limit form recovery**: No shared budget is spent on browser state that
  the results navigation does not consume.
- **Preserve historical step vocabulary**: Existing stored traces and agent unit tests remain readable,
  while new journey runs emit only active steps.
- **Fail closed**: No property, context, room, refundability, currency, or savings gate was relaxed.

### Deviations from Plan

None.

### Dependencies Added

None.

### Developer Notes

The focused implementation suite contains 20 passing tests. Full-suite and static verification belong
to the next mandatory Test stage after human approval of this implementation checkpoint.
