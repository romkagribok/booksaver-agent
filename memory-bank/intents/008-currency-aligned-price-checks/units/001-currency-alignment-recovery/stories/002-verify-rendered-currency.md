---
id: 002-verify-rendered-currency
unit: 001-currency-alignment-recovery
intent: 008-currency-aligned-price-checks
status: complete
priority: must
created: 2026-07-19T00:32:13.000Z
assigned_bolt: 020-currency-alignment-recovery
implemented: true
---

# Story: Verify Rendered Candidate Currencies

**Global story ID**: US-058

## User Story

**As a** BookSaver user
**I want** comparisons authorized by the currency actually shown for the room offer
**So that** a requested preference cannot create a false savings result when Booking.com ignores it

## Acceptance Criteria

- [ ] Every parsed offer candidate carries its rendered ISO-4217 currency.
- [ ] Same-currency eligibility remains after positive refundability, room match, and confidence gates.
- [ ] Selection exposes candidates that passed every preceding gate and failed only currency.
- [ ] Other candidates retain their original exclusion reason and cannot spur currency recovery.

## Technical Notes

- Preserve the existing first-failing-gate semantics for ordinary exclusion summaries.
- Add explicit pure selection evidence rather than inferring eligibility from formatted detail strings.

## Dependencies

### Requires

- US-019 equivalent-offer extraction and US-057 trusted currency request.

### Enables

- US-059 bounded recovery and US-060 specific failure reporting.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Refundable room matches but uses EUR against USD baseline | Expose as currency-only mismatch |
| Non-refundable offer also has a different currency | Retain `not_refundable`; do not trigger recovery from it |
| Room mismatch uses another currency | Retain `room_mismatch`; do not treat it as alignment evidence |

## Out of Scope

- Deciding whether an exchange rate makes unlike currencies economically comparable.
