---
intent: 007-telegram-on-demand-checks
created: 2026-07-18T23:40:00Z
status: complete
---

# Units: Telegram On-Demand Checks

## Requirement-to-Unit Mapping

- **FR-1** → `001-on-demand-check-orchestration`
- **FR-2** → `001-on-demand-check-orchestration`
- **FR-3** → `001-on-demand-check-orchestration`
- **FR-4** → `001-on-demand-check-orchestration`
- **FR-5** → `001-on-demand-check-orchestration`

## Unit 001: On-Demand Check Orchestration

- **Purpose**: Add caller-scoped `/checknow` while consolidating scheduled and immediate monitor work
  behind one safe coordinator.
- **Unit Type**: Application service and Telegram inbound adapter.
- **Default Bolt Type**: `simple-construction-bolt`.
- **Dependencies**: Search monitor/agent escalation, per-user limits/notifier routing, Telegram command
  navigation, production-hardening search entry, and conversational booking ownership.
- **Interface**: `/checknow`, `checknow:` callbacks, scheduler job callable, coordinator request/result.

## Independence

The unit is one cohesive runtime boundary: the user-facing feature is unsafe without the shared
coordinator refactor, and the refactor is validated through the scheduled and on-demand callers
together. It adds no schema or deployment component.
