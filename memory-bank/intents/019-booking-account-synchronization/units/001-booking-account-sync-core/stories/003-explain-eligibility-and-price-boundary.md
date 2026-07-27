---
id: 003-explain-eligibility-and-price-boundary
unit: 001-booking-account-sync-core
intent: 019-booking-account-synchronization
status: complete
priority: must
created: 2026-07-27T16:28:04.000Z
assigned_bolt: 034-booking-account-sync-core
implemented: true
---

# Story: US-114 Explain eligibility and preserve price-source boundaries

## User Story

**As a** BookSaver user
**I want** every reservation classified with precise eligibility reasons
**So that** I understand what can be checked and why other reservations cannot.

## Acceptance Criteria

- [ ] Eligibility requires active future refundable hotel state plus every trusted comparison fact.
- [ ] Missing, ambiguous, unsupported, past, cancelled, non-refundable, absent, and stale conditions
  remain distinguishable.
- [ ] Multiple reason codes are stable, testable, and caller-visible.
- [ ] Account-page price is accepted only as booked baseline, never as candidate offer.
- [ ] Eligible snapshots continue through the established authenticated customer-search gates.
- [ ] Quotas and technical failures remain separate from intrinsic eligibility.

## Dependencies

### Requires
- US-112 and US-113.

### Enables
- US-116 and US-117.

## Out of Scope

- Telegram layout or candidate-offer extraction changes.
