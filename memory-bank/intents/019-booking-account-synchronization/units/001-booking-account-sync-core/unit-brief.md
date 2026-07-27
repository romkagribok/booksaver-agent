---
unit: 001-booking-account-sync-core
intent: 019-booking-account-synchronization
phase: inception
status: complete
unit_type: cli
default_bolt_type: ddd-construction-bolt
created: 2026-07-27T16:28:04.000Z
updated: 2026-07-27T16:28:04.000Z
---

# Unit Brief: Booking Account Sync Core

## Purpose

Turn a caller's authenticated Booking.com hotel-reservation inventory into authoritative,
caller-scoped local snapshots without granting BookSaver any reservation-mutation authority.

## Scope

### In Scope

- Complete/partial/failed inventory evidence and bounded read-only discovery.
- Stable remote identity, reservation facts, lifecycle, freshness, and eligibility reasons.
- Atomic idempotent reconciliation and current-savings invalidation.
- Destructive removal of all pre-cutover legacy booking state.
- Redacted audit, recovery outcomes, and price-source separation.

### Out of Scope

- Telegram trigger/UI orchestration.
- Manual booking CRUD, guided rebooking, or any Booking.com mutation.
- Non-hotel products, native apps, private APIs, or receipt/email import.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Synchronize complete authenticated hotel inventory | Must |
| FR-2 | Preserve remote identity and synchronized snapshots | Must |
| FR-3 | Classify and explain monitoring eligibility | Must |
| FR-5 | Reconcile without false deletion or replacement inference | Must |
| FR-6 | Preserve the verified live-price boundary | Must |
| FR-10 | Remove legacy booking state at cutover | Must |
| FR-11 | Recover visibly from synchronization failures | Must |

## Domain Concepts

| Concept | Description |
|---------|-------------|
| Remote reservation identity | Caller-scoped Booking.com identity used for idempotent upsert |
| Inventory observation | Validated reservation facts plus lifecycle and provenance |
| Inventory completeness | Complete, incomplete, or failed traversal evidence |
| Synchronized snapshot | Local immutable-to-users view of authoritative remote facts |
| Eligibility decision | Eligible or reason-coded ineligible/indeterminate result |
| Synchronization run | Triggered, bounded, auditable reconciliation attempt |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 4 |
| Must Have | 4 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-112 | Discover the complete authenticated reservation inventory | Must | Ready |
| US-113 | Reconcile remote reservation snapshots atomically | Must | Ready |
| US-114 | Explain eligibility and preserve price-source boundaries | Must | Ready |
| US-115 | Cut over legacy state and recover from synchronization failures | Must | Ready |

## Dependencies

- ADR-004, ADR-007, ADR-008, ADR-013/020, ADR-016, ADR-021, ADR-024, ADR-025, ADR-026.
- Existing encrypted per-user session vault, synchronous Playwright coordinator, SQLite repositories,
  savings currentness, and schema migration chain.

## Success Criteria

- [ ] Complete inventory discovery is proven against representative authenticated fixtures and a
  real-account acceptance gate.
- [ ] Partial traversal cannot make unseen reservations inactive.
- [ ] Remote identity upsert and eligibility are deterministic and caller-scoped.
- [ ] Legacy booking rows and dependent history are removed atomically while users/sessions remain.
- [ ] Account pages never become candidate-price sources or mutation surfaces.
- [ ] Focused and full quality gates pass.

## Bolt Suggestions

- `034-booking-account-sync-core`: feasibility, domain, port, and inventory adapter.
- `035-booking-account-sync-core`: persistence reconciliation, eligibility, migration, and failures.
