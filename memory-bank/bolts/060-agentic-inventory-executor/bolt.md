---
id: 060-agentic-inventory-executor
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 006-execute-bookings-inventory-with-browser-use
created: 2026-08-30T18:00:44.000Z
started: 2026-08-30T18:02:59.000Z
completed: "2026-08-30T18:43:57Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-08-30T18:07:00.000Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-30T18:14:00.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-30T18:15:00.000Z
    artifact: adr-041-trigger-specific-browser-use-for-bookings.md
requires_bolts:
  - 053-agentic-inventory-executor
  - 056-agentic-inventory-executor
  - 057-agentic-inventory-executor
  - 058-agentic-inventory-executor
  - 059-agentic-inventory-executor
enables_bolts: []
requires_units:
  - 001-agentic-executor-control-plane
  - 002-local-agentic-price-executor
blocks: false
complexity:
  avg_complexity: 4
  avg_uncertainty: 3
  max_dependencies: 3
  testing_scope: 5
---

# Bolt: Browser Use `/bookings` Inventory Executor

## Objective

Add a pinned local Browser Use OSS adapter for Telegram `/bookings` only, behind the existing
inventory executor port and every current BookSaver trust, privacy, cost, and reconciliation
boundary.

## Stories Included

- [x] **US-160**: Execute `/bookings` inventory with Browser Use - Priority: Must

## Expected Outputs

- Trigger-specific Browser Use inventory adapter and coordinator composition.
- Closed, deny-oriented read-only Browser Use tool/action guard.
- Existing typed inventory observations, cost accounting, session proof, and transient teardown.
- Telemetry/content-persistence confinement and dependency/exact-image qualification.
- AI-DLC DDD artifacts, tests, Bugbot-clean merge, and production deployment evidence.

## Dependencies

- Bolts 053 and 056 through 059 are complete.
- ADR-036 through ADR-040 remain binding.

## Success Criteria

- [x] `/bookings` invokes Browser Use and no other trigger does.
- [x] Ordinary read-only Booking.com presentation churn does not require exact selector/label/path
  maintenance.
- [x] Every unsafe tool, action, destination, popup, privacy leak, and limit breach fails closed.
- [x] Existing Stagehand, price, validation, positive-only reconciliation, and rollback behavior are
  unchanged.
- [x] Focused, repository-wide, AI-DLC, dependency, exact-image, egress, and pre-merge gates pass;
  Bugbot and production Telegram acceptance remain release gates.
