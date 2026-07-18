---
id: 005-enter-search-from-trusted-query
unit: 001-production-reliability
intent: 004-production-hardening
status: complete
priority: must
created: 2026-07-18T18:57:24Z
assigned_bolt: 014-production-reliability
implemented: true
---

# Story: Enter Search From Trusted Query

**Global story ID**: US-041

## User Story

**As a** Telegram user monitoring a registered booking
**I want** BookSaver to begin each live-price search from an exact Booking.com results query
**So that** homepage form drift cannot consume the budget needed to inspect and interpret the
property's actual room offers

## Acceptance Criteria

- [ ] **Given** a booking has persisted property, stay-date, and occupancy data, **When** its search
  journey begins, **Then** BookSaver navigates directly to Booking.com's read-only search-results URL
  constructed only from those trusted values, without filling or submitting the homepage form.
- [ ] **Given** direct results navigation succeeds, **When** the journey continues, **Then** it still
  locates the exact property in Booking.com's result cards, opens the fresh result link, verifies the
  requested dates and occupancy, and reads the room/rate view before extracting an offer.
- [ ] **Given** results, property navigation, context verification, or room-table interpretation
  differs from known scripted behavior, **When** that named step fails, **Then** the existing guarded,
  screenshot-capable LLM recovery remains available within the shared hard budget.
- [ ] **Given** the search query returns the wrong property/context, no availability, a bot wall, or
  no equivalent refundable offer, **When** the check is evaluated, **Then** it fails closed and creates
  no savings opportunity.
- [ ] **Given** a successful equivalent refundable live offer, **When** savings are evaluated,
  **Then** the existing baseline comparison and Telegram notification behavior is unchanged.

## Technical Notes

- Reuse `_search_results_url(booking)` as the sole source of query parameters.
- Remove the homepage/form steps from active journey execution; do not retain an LLM form-repair
  detour before results navigation.
- Preserve named downstream journey seams and the existing ActionGuard, trace, budget, extraction,
  equivalence, and savings-pipeline contracts.
- Record the deliberate amendment to ADR-013, whose original sequence required homepage form entry.

## Dependencies

### Requires

- US-018 and US-019: verified search journey and equivalent-offer extraction.
- US-020 through US-022: guarded LLM recovery, budgets, and traces.
- US-038: trusted-data URL continuation, now promoted from late fallback to primary entry.

### Enables

- Live VPS checks that reserve their LLM/time budget for ambiguous downstream pages.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Property-name query is ambiguous | Exact normalized result-card matching must succeed or the check fails |
| Booking.com drops query parameters | Context verification fails before offer extraction |
| Results page layout changes | The `submit_search`/`locate_property` escalation seam invokes guarded LLM recovery |
| Property has no inventory for the stay | Record a closed failure/no-equivalent outcome; never invent a price |

## Out of Scope

- Direct navigation to a registered property URL as the price source.
- Using search-card headline prices as savings evidence.
- Weakening property, date, occupancy, room, currency, or refundability checks.
- Increasing hard agent budgets or adding an autonomous booking action.
