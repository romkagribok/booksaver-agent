---
unit: 001-agentic-executor-control-plane
intent: 023-replaceable-agentic-browser-executor
phase: inception
status: complete
created: '2026-08-16T19:18:41Z'
updated: '2026-08-16T19:18:41Z'
unit_type: backend
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: Agentic Executor Control Plane

## Purpose

Create the provider-neutral boundary that lets BookSaver consume untrusted browser observations
without yielding session, safety, pricing, equivalence, persistence, or routing authority.

## Scope

### In Scope

- Executor request/result types, terminal outcomes, session lease, and fake executor.
- Independent evidence validation and conversion to existing offer evaluation inputs.
- Shared action/time/cost limits and exact accounting.
- `legacy`, `owner_canary`, and `agentic` routing policy with legacy default.

### Out of Scope

- Stagehand or Anthropic provider implementation (unit 002).
- Live qualification and promotion approval (unit 003).
- Inventory migration (unit 004).

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Provider-neutral price browser executor | Must |
| FR-2 | BookSaver-owned validation and evaluation | Must |
| FR-3 | Owner-bound transient session lease | Must |
| FR-6 | Exact action, time, and cost accounting | Must |
| FR-7 | Incremental routing and rollback | Must |

## Domain Concepts

- **PriceExecutionRequest**: Trusted query, opaque session lease, and exact limits.
- **PriceExecutionResult**: Terminal metadata and untrusted typed observations.
- **ObservedOffer**: Visible room/refundability/all-in price evidence without equivalence claims.
- **SessionLease**: One job, one owner, one transient browser, unconditional teardown.
- **ExecutionRoutingPolicy**: Closed mode plus role/consent/qualification admission.

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 4 |
| Must Have | 4 |
| Should Have | 0 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-143 | Define the executor evidence contract | Must | Complete |
| US-144 | Validate every observation independently | Must | Complete |
| US-145 | Lease transient owner sessions safely | Must | Complete |
| US-146 | Route and account for bounded execution | Must | Complete |

## Dependencies

- Existing `CheckCoordinator`, user/session services, offer policy, model budget, and legacy monitor.
- Depended on by units 002 and 003.

## Constraints

- Provider objects and session bytes never cross the port.
- No production routing changes in this unit.
- All ambiguity fails closed.

## Success Criteria

- [ ] Contract/fake tests cover every terminal outcome and sensitive-field rejection.
- [ ] Conflicting evidence cannot become an `OfferCandidate`.
- [ ] Exact limits are reserved and reconciled without overrun.
- [ ] Legacy remains default and invited users cannot enter owner canary.

## Bolt Suggestions

- `050-agentic-executor-control-plane`: US-143 through US-146.
