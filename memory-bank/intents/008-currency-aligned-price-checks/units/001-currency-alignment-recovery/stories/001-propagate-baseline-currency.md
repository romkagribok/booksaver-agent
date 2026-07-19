---
id: 001-propagate-baseline-currency
unit: 001-currency-alignment-recovery
intent: 008-currency-aligned-price-checks
status: complete
priority: must
created: 2026-07-19T00:32:13.000Z
assigned_bolt: 020-currency-alignment-recovery
implemented: true
---

# Story: Propagate Baseline Currency Through Trusted Navigation

**Global story ID**: US-057

## User Story

**As a** BookSaver user whose daemon runs in another locale
**I want** every live search to request my booking's original currency
**So that** Booking.com does not localize a comparable offer into an unusable currency by default

## Acceptance Criteria

- [ ] The trusted search-results URL requests the booking's baseline ISO-4217 currency.
- [ ] The final property URL requests the same currency while preserving exact dates and occupancy.
- [ ] Conflicting currency context from a result-card link cannot override the persisted baseline.
- [ ] Existing Booking.com host validation and read-only navigation protections remain unchanged.

## Technical Notes

- Currency is trusted persisted context alongside dates and occupancy.
- Isolate Booking.com's currency-preference query representation behind a small helper.

## Dependencies

### Requires

- US-041 trusted-query search entry.

### Enables

- US-058 rendered-currency verification.
- US-059 bounded alignment recovery.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Result href contains another requested currency | Replace it with baseline currency |
| Baseline uses lowercase user input originally | Persisted `Money` supplies normalized uppercase ISO code |
| Unsafe non-Booking.com result href | Existing host guard rejects it before navigation |

## Out of Scope

- Treating a requested query parameter as proof that the page honored the currency.
- Converting the baseline into the VPS locale.
