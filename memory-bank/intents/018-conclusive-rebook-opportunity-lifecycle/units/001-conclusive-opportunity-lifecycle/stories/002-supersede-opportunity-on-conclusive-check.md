---
id: 002-supersede-opportunity-on-conclusive-check
unit: 001-conclusive-opportunity-lifecycle
intent: 018-conclusive-rebook-opportunity-lifecycle
status: complete
priority: must
created: 2026-07-27T02:32:08.000Z
assigned_bolt: 033-conclusive-opportunity-lifecycle
implemented: true
---

# Story: Supersede Opportunity on Conclusive Check

**Global story ID**: US-110

## User Story

**As a** user reviewing current savings
**I want** the latest conclusive price state to replace an older quote
**So that** `/rebook` reflects what BookSaver most recently established about the market.

## Acceptance Criteria

- [x] A newer successful cheaper price replaces the old opportunity even when the saving shrinks.
- [x] A newer successful price at or above baseline leaves no current opportunity.
- [x] A newer `NO_EQUIVALENT_OFFER` leaves no current opportunity.
- [x] A later successful saving restores a current opportunity.
- [x] Persisted check insertion order resolves equal timestamps.

## Dependencies

US-109 and the check-to-opportunity linkage.
