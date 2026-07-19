---
id: 004-report-unresolved-currency
unit: 001-currency-alignment-recovery
intent: 008-currency-aligned-price-checks
status: ready
priority: must
created: 2026-07-19T00:32:13Z
assigned_bolt: 020-currency-alignment-recovery
implemented: false
---

# Story: Report Unresolved Currency Alignment Safely

**Global story ID**: US-060

## User Story

**As a** BookSaver user or VPS operator
**I want** an unresolved currency mismatch reported explicitly
**So that** I know an offer was found but could not be compared safely

## Acceptance Criteria

- [ ] Persistent mismatch produces a stable currency-specific check classification.
- [ ] Failure detail includes the baseline currency, observed mismatched currencies, and recovery result.
- [ ] Traces record the requested currency, recovery start/method, and terminal verification outcome.
- [ ] `/checknow` returns the actionable failure plus check ID prefix through the existing formatter.
- [ ] Scheduled checks persist the same classification and evidence without producing savings.

## Technical Notes

- Keep Telegram concise; detailed observed candidates belong in persisted trace/detail.
- Do not overload `no_equivalent_offer` when currency alignment is the terminal cause.

## Dependencies

### Requires

- US-058 currency-only evidence and US-059 recovery outcome.

### Enables

- Operational diagnosis and future Booking.com currency-mechanism maintenance.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Several currency-only candidates share one currency | Report that observed currency once |
| Candidates contain multiple mismatched currencies | Report sorted unique currencies deterministically |
| Telegram delivery fails | Check and trace remain persisted through existing behavior |

## Out of Scope

- Claiming a saving or loss using the mismatched amounts.
