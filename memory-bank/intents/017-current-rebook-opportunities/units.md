---
intent: 017-current-rebook-opportunities
phase: inception
status: units-decomposed
updated: 2026-07-27T02:10:44Z
---

# Current Rebook Opportunities - Unit Decomposition

## Units Overview

This corrective intent contains one cohesive command/repository unit.

### Unit 1: `001-current-rebook-opportunities`

**Description**: Define and enforce the newest-per-active-booking action policy across the SQLite
repository, Telegram picker, and shared guided-rebook service.

**Assigned Requirements**: FR-1 through FR-3.

**Deliverables**:

- One-query current opportunity selection for owned active bookings.
- Telegram picker with one choice per booking.
- Application-level rejection of superseded opportunity IDs.
- Persistence, service, Telegram, privacy, and historical-audit regression tests.

**Dependencies**:

- Existing savings persistence and append-only check pipeline.
- Existing Telegram `/rebook` callback flow and guided rebook confirmation service.
- ADR-023 stale-action and audit-history boundary.

## Requirement-to-Unit Mapping

- **FR-1**: Select one newest opportunity per active booking → `001-current-rebook-opportunities`
- **FR-2**: Reject superseded selections at execution time → `001-current-rebook-opportunities`
- **FR-3**: Preserve audit and access boundaries → `001-current-rebook-opportunities`

## Execution Order

Execute one simple construction bolt: `032-current-rebook-opportunities`.
