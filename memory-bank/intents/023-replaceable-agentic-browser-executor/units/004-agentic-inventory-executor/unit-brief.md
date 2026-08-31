---
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
phase: inception
status: complete
created: 2026-08-25T13:00:00.000Z
updated: 2026-08-30T22:28:13.000Z
unit_type: backend
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: Agentic Inventory Executor

## Purpose

Replace selector-dependent Booking.com inventory perception with a provider-neutral Stagehand
capability for every disclosed authorized user, while BookSaver retains session custody,
validation, positive-only reconciliation, scheduling, and check authority.

## Scope

### In Scope

- `InventoryBrowserExecutor` request/result contracts and fake executor.
- Account-bound transient session leases and inventory-specific action/destination guards.
- Stagehand semantic scope, pagination, detail navigation, and typed extraction.
- One guarded Anthropic computer-use fallback without typing.
- Positive-only reconciliation and current-run check eligibility.
- `/bookings`, post-connect, `/checknow`, and scheduled routing.
- One inventory execution for a selected `/checknow` operation.
- Capability-specific config, rollback, redacted metrics, and tests.
- Layered destination admission that tolerates benign Booking.com route/query churn for perception
  without granting interaction authority.
- Sanitized destination rejection logs that retain no raw URLs, values, or page/session content.
- Thread-owned persistent cost admission and reconciliation across the async Stagehand boundary.
- Provider-compatible typed extraction and computer-use tool schemas with code-owned bounds.
- Version-matched mobile browser identity across `/connect`, session verification, and Stagehand.
- Typed, content-free browser navigation failures before semantic or computer-use execution.
- Trigger-specific local Browser Use OSS execution for Telegram `/bookings`.
- Code-owned canonical HTTPS inventory entry that avoids Booking.com's blocked legacy HTTP
  redirect without permitting HTTP browser egress.

### Out of Scope

- Model-authorized absence reconciliation or deletion of unseen rows.
- `/connect` authentication changes.
- Price routing, price promotion, or legacy price-selector removal.
- Selector learning, cached actions, managed browsers, or new provider secrets.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-10 | Provider-neutral agentic inventory execution | Must |
| FR-12 | Browser Use execution for `/bookings` | Must |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 7 |
| Must Have | 7 |
| Should Have | 0 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-153 | Execute positive-only agentic inventory | Must | Complete |
| US-156 | Tolerate read-only destinations and diagnose rejections | Must | Complete |
| US-157 | Keep agentic cost accounting thread-affine | Must | Complete |
| US-158 | Use provider-compatible agentic schemas | Must | Complete |
| US-159 | Preserve mobile session identity and classify navigation failure | Must | Complete |
| US-160 | Execute `/bookings` inventory with Browser Use | Must | Complete |
| US-161 | Enter Browser Use inventory through canonical HTTPS | Must | In progress |

## Dependencies

- Units 001 and 002.
- Existing account synchronization, ADR-027 projection, and ADR-028 reconciliation rules.
- Existing disclosure, session vault, cost ledger, coordinator gate, and transient Chromium runtime.

## Constraints

- Every authorized disclosed user uses agentic inventory; price routing remains independent.
- Only current-run positive observations may unblock a check.
- Unseen rows are always preserved by this capability.
- Inventory and price in one operation share cost admission and deadline.
- Inventory computer use cannot type.
- Observation admission is weaker than interaction admission; exact provider paths and benign query
  keys are not long-lived safety boundaries.
- Raw URLs, query values, fragments, and page/session content never enter destination diagnostics.
- SQLite's default thread-affinity protection remains enabled; connections are never shared across
  the coordinator and async browser threads.
- Provider SDK schema subsets never weaken BookSaver's post-decode validation or positive-only
  reconciliation authority.
- Browser Use is selected only for `/bookings`, cannot silently fall back within the same job, and
  receives no cloud, persistent-history, or unsafe default tools.

## Success Criteria

- [x] DOM-resilience fixtures pass without BookSaver inventory selectors.
- [x] All inventory triggers use the executor with one `/checknow` inventory run.
- [x] Current-run positives can proceed while cached-only rows cannot.
- [x] No agentic terminal can mark an unseen reservation absent.
- [x] Session, action, destination, privacy, cost, timeout, and teardown tests pass.

## Bolt Suggestions

- `053-agentic-inventory-executor`: US-153.
- `056-agentic-inventory-executor`: US-156 production destination-policy correction after live
  `non_allowlisted_destination` evidence.
- `057-agentic-inventory-executor`: US-157 production cost-ledger thread-affinity correction after
  live `sqlite3.ProgrammingError` evidence.
- `058-agentic-inventory-executor`: US-158 Stagehand and Anthropic schema-compatibility correction
  after live pre-inference provider rejections.
- `059-agentic-inventory-executor`: US-159 mobile session identity and navigation-failure
  correction after the live Booking.com OAuth loop.
- `060-agentic-inventory-executor`: US-160 trigger-specific local Browser Use execution for
  `/bookings` without changing the inventory port or other routes.
- `061-agentic-inventory-executor`: US-161 production correction for the blocked legacy HTTP
  redirect at Browser Use inventory entry.
