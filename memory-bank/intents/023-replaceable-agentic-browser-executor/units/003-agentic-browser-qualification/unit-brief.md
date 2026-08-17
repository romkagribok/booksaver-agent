---
unit: 003-agentic-browser-qualification
intent: 023-replaceable-agentic-browser-executor
phase: inception
status: in-progress
created: 2026-08-16T19:18:41Z
updated: 2026-08-17T04:21:00Z
unit_type: backend
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: Agentic Browser Qualification

## Purpose

Make promotion evidence-based by testing DOM resilience, privacy, safety, reliability, cost, and
duration and by requiring a real owner-only canary before invited-user routing.

## Scope

### In Scope

- DOM-resilience fixtures and forced visual fallback fixture.
- Egress, session-leak, prohibited-action, budget, timeout, and teardown tests.
- Redacted canary ledger, threshold evaluator, and automatic fail-closed routing response.
- Human comparison records without stored page content or screenshots.

### Out of Scope

- Simulating or fabricating 14 days of live evidence.
- Automatically promoting invited users.
- Post-promotion inventory migration (unit 004).

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-9 | Qualification and automatic regression response | Must |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 2 |
| Must Have | 2 |
| Should Have | 0 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-151 | Prove DOM resilience and privacy boundaries | Must | Complete |
| US-152 | Govern live canary promotion and regression rollback | Must | In progress |

## Dependencies

- Units 001 and 002.
- Deployment owner for manual Booking.com comparisons and explicit promotion approval.

## Constraints

- Qualification records contain metrics and closed outcomes only.
- Any safety/privacy/correctness violation is terminal regardless of aggregate reliability.
- Owner canary cannot authorize invited users until thresholds and consent both pass.

## Success Criteria

- [x] Offline fixtures exercise all named DOM variations without BookSaver selectors.
- [x] Egress and sensitive-content tests prove the accepted privacy boundary.
- [x] Threshold evaluator exactly implements all promotion gates.
- [ ] Live gate remains pending until authentic owner evidence exists.

## Bolt Suggestions

- `052-agentic-browser-qualification`: US-151 and US-152 after bolt 051.
