---
intent: 018-conclusive-rebook-opportunity-lifecycle
phase: inception
status: units-decomposed
updated: 2026-07-27T02:32:08Z
---

# Conclusive Rebook Opportunity Lifecycle - Unit Decomposition

## Units Overview

### Unit 1: `001-conclusive-opportunity-lifecycle`

**Description**: Derive and enforce actionable savings from the latest conclusive market check while
preserving prior positive evidence across technical failures.

**Assigned Requirements**: FR-1 through FR-3.

**Deliverables**:

- Check-linked SQLite current-opportunity queries.
- Conclusive-success and `NO_EQUIVALENT_OFFER` invalidation.
- Technical-failure preservation.
- Matching application, Telegram, and atomic session guards.
- Persistence, race, history, and privacy regression tests.

**Dependencies**:

- Intent 017 current-per-booking selection.
- Existing check-history and savings-opportunity linkage.
- ADR-023 audit-history versus stale-action boundary.

## Requirement-to-Unit Mapping

- **FR-1**: Preserve across technical failures → `001-conclusive-opportunity-lifecycle`
- **FR-2**: Supersede on conclusive observations → `001-conclusive-opportunity-lifecycle`
- **FR-3**: Enforce at every rebook boundary → `001-conclusive-opportunity-lifecycle`

## Execution Order

Execute one simple construction bolt: `033-conclusive-opportunity-lifecycle`.
