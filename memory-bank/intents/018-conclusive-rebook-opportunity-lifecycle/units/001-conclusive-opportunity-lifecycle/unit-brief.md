---
unit: 001-conclusive-opportunity-lifecycle
intent: 018-conclusive-rebook-opportunity-lifecycle
phase: inception
status: complete
unit_type: cli
default_bolt_type: simple-construction-bolt
created: 2026-07-27T02:32:08.000Z
updated: 2026-07-27T02:46:10Z
---

# Unit Brief: Conclusive Opportunity Lifecycle

## Purpose

Make current rebook actionability reflect the latest conclusive market evidence rather than the
latest check attempt or merely the latest historical positive row.

## Scope

### In Scope

- Check-history-linked current opportunity queries.
- Explicit conclusive-result classification.
- Technical-failure preservation.
- Successful smaller-saving replacement and conclusive invalidation.
- Telegram, service, and transactional guard consistency.
- Historical and ownership regression coverage.

### Out of Scope

- Live checking from `/rebook`.
- Age expiry or destructive cleanup.
- Extraction and price-comparison changes.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Preserve across technical failures | Must |
| FR-2 | Supersede on conclusive market observations | Must |
| FR-3 | Enforce at every rebook boundary | Must |

## Key Operations

| Operation | Input | Output |
|-----------|-------|--------|
| Classify persisted result | outcome and failure code | conclusive or technical |
| Resolve current opportunity | booking ID | latest conclusive positive opportunity or none |
| List current choices | local user ID | zero or one row per active owned booking |
| Start guarded session | selected opportunity | inserted session or safe stale rejection |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 3 |
| Must Have | 3 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 001-preserve-opportunity-across-technical-failures | Preserve opportunity across technical failures | Must | Complete |
| 002-supersede-opportunity-on-conclusive-check | Supersede opportunity on conclusive check | Must | Complete |
| 003-enforce-conclusive-currentness-atomically | Enforce conclusive currentness atomically | Must | Complete |

## Technical Context

Use the savings row's `check_id` to join its originating `check_history.id`. A row is current only
when no later conclusive check exists for the booking. Treat persisted success and
`failure_code = no_equivalent_offer` as conclusive. Keep all other failures outside the superseding
set. Reuse this predicate in list, lookup, and transactional session insertion queries.

## Success Criteria

- [x] Technical failures preserve the last conclusive positive choice.
- [x] Later successful smaller savings replace larger historical savings.
- [x] Later successful non-saving and `NO_EQUIVALENT_OFFER` results remove actionability.
- [x] A later positive success restores actionability.
- [x] All rebook validation layers agree and history remains intact.
- [x] Focused and full quality gates pass.
- [ ] Final product-owner merge review is complete.

## Bolt Suggestion

`033-conclusive-opportunity-lifecycle` — Simple Construction, all three stories.
