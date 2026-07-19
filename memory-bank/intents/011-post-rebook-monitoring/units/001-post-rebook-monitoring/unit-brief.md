---
unit: 001-post-rebook-monitoring
intent: 011-post-rebook-monitoring
phase: inception
status: complete
unit_type: cli
default_bolt_type: ddd-construction-bolt
created: 2026-07-19T19:50:29.000Z
updated: 2026-07-19T20:23:12Z
---

# Unit Brief: Post-Rebook Monitoring

## Purpose

Turn a successfully completed device-side rebook into the new monitored reservation without trusting
the detected offer as a receipt, losing history, retaining stale savings, or leaving a cancelled old
reservation active after a partial flow.

## Scope

### In Scope

- Independent cancellation/replacement outcome capture.
- Actual confirmation, same-property Booking.com URL, and actual all-in Money dialog.
- Stable-ID replacement propagation and cancellation-only archival.
- Transactional active-user/ownership/session/snapshot validation.
- Stale-savings invalidation, retained history, audit disposition, and user-facing recovery messages.

### Out of Scope

- Booking.com receipt verification or authenticated reservation import.
- Automatic cancellation/purchase or changing the stay/room/occupancy equivalence criteria.
- Additional Telegram commands, web UI, or schema migration.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Collect actual replacement reservation facts | Must |
| FR-2 | Atomically propagate a valid replacement | Must |
| FR-3 | Reconcile the complete partial-outcome matrix | Must |
| FR-4 | Invalidate stale savings and preserve audit history | Must |
| FR-5 | Preserve ownership, revocation, and visible completion boundaries | Must |

## Domain Concepts

| Concept | Description | Key attributes |
|---------|-------------|----------------|
| Replacement facts | Facts established only after checkout | confirmation, canonical property URL, actual Money |
| Source snapshot | Monitored booking handed to the user before external actions | booking identity and all monitoring fields |
| Outcome report | Independent user report for cancellation/replacement handoff | completed/abandoned/unreported |
| Monitoring disposition | Safe result of reconciling outcomes/facts | replacement active/original active/no active booking |
| Propagation audit | Durable explanation of monitoring-state change | session, disposition, actual total, timestamp |

## Key Operations

| Operation | Inputs | Output |
|-----------|--------|--------|
| Validate replacement facts | text answers + source snapshot | validated actual replacement |
| Archive cancelled source | owner/session/source snapshot | archived booking + invalidated savings + audit |
| Propagate replacement | owner/session/source snapshot + replacement | active updated booking + invalidated savings + audit |
| Reconcile outcome | cancellation/replacement report | disposition and recovery message |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 5 |
| Must Have | 5 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-072 | Collect actual replacement facts | Must | Ready |
| US-073 | Propagate monitored replacement atomically | Must | Ready |
| US-074 | Reconcile partial outcomes safely | Must | Ready |
| US-075 | Preserve audit and invalidate stale savings | Must | Ready |
| US-076 | Preserve ownership, revocation, and visible completion | Must | Ready |

## Dependencies

- Bolt 011: Telegram gate, handoff, callback bridge, and rebook audit.
- Bolt 017: Booking mutation and stale-savings principles.
- Bolt 022: Private-chat ownership and asynchronous revocation guards.
- ADR-001, ADR-004, ADR-012, ADR-022.

## Technical Context

Use a small application/domain reconciliation service, a Telegram `DialogDefinition`, and additive
SQLite repository operations. The final mutation uses one immediate transaction and a stable booking
ID. No schema or third-party dependency is required.

## Constraints

- Do not derive the actual baseline from `SavingsOpportunity.live_price`.
- Do not mutate without explicit reported completion, valid facts, and final confirmation.
- Do not delete check/rebook audit history.
- Do not notify or mutate after revocation.

## Success Criteria

- [ ] All nine cancellation/replacement outcome combinations are deterministic and tested.
- [ ] Successful propagation feeds future checks the actual new baseline.
- [ ] Cancellation without a validated replacement cannot leave the old booking active.
- [ ] Concurrency, ownership, revocation, duplicate confirmation, and stale snapshot fail atomically.
- [ ] Full quality gates pass.

## Bolt Suggestion

- `023-post-rebook-monitoring` — DDD construction bolt covering US-072 through US-076.
