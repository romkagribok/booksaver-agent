---
id: 002-continue-fill-search-from-trusted-data
unit: 001-production-reliability
intent: 004-production-hardening
status: ready
priority: must
created: 2026-07-18T17:48:48Z
assigned_bolt: 013-production-reliability
implemented: false
---

# Story: Continue Fill Search From Trusted Data

**Global story ID**: US-038

## User Story

**As a** Telegram user monitoring a registered booking
**I want** a check to continue safely when the LLM cannot operate Booking.com's changed calendar
**So that** ordinary layout drift does not prevent BookSaver from finding a verified equivalent offer

## Acceptance Criteria

- [ ] **Given** scripted `fill_search` fails, **When** recovery begins, **Then** the screenshot-aware
  LLM is attempted before any deterministic continuation.
- [ ] **Given** `fill_search` recovery ends with `AGENT_GAVE_UP` or `BUDGET_EXCEEDED`, **When** the
  journey continues, **Then** it uses the existing exact search URL built only from persisted
  property, date, and occupancy data.
- [ ] **Given** recovery ends with `BLOCKED_ACTION`, a navigation/bot-wall failure, or failure in a
  later step, **When** the journey evaluates the result, **Then** the check remains failed.
- [ ] **Given** exact-URL navigation succeeds, **When** the page is evaluated, **Then** normal
  property identity and search-context verification occurs before offer extraction.
- [ ] **Given** a mismatched property, date, room context, or offer, **When** downstream verification
  runs, **Then** no savings opportunity is created.

## Technical Notes

- Reuse the existing read-only search URL builder rather than creating another navigation strategy.
- Limit the exception to the `FILL_SEARCH` step and two explicitly enumerated bounded failure codes.
- Record the fallback in journey trace detail for operator diagnosis.

## Dependencies

### Requires

- 001-adapt-after-repeated-browser-actions.
- Intent 002, US-018 and US-019 (completed search journey and equivalence pipeline).

### Enables

- Reliable production checks from the VPS after deployment.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Persisted dates are invalid or no longer accepted | Navigation/context verification fails the check normally |
| Booking.com rewrites or drops query parameters | Search-context verification fails closed |
| LLM successfully completes `fill_search` | Continue normally; do not invoke the exact-data fallback |

## Out of Scope

- Skipping search-context or property verification.
- Agent-generated changes to registered dates or occupancy.
- Fallbacks for result selection, property verification, or room extraction failures.
