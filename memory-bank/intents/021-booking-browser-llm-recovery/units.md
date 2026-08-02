---
intent: 021-booking-browser-llm-recovery
phase: inception
status: units-decomposed
updated: 2026-08-02T18:07:49Z
---

# Booking Browser LLM Recovery - Unit Decomposition

## Requirement-to-Unit Mapping

- **FR-1**: Report verified browser-action outcomes → `001-shared-booking-browser-recovery`
- **FR-2**: Detect semantic no-progress and terminate accurately → `001-shared-booking-browser-recovery`
- **FR-3**: Use step-specific, evidence-rich LLM recovery → `001-shared-booking-browser-recovery`
- **FR-4**: Back every automated Booking.com browser journey with guarded recovery → `001-shared-booking-browser-recovery`
- **FR-5**: Resolve LLM capability and usage by caller and operation → `001-shared-booking-browser-recovery`
- **FR-6**: Recover account inventory navigation and interpretation → `002-agent-assisted-booking-inventory`
- **FR-7**: Preserve authoritative completeness and safety boundaries → `002-agent-assisted-booking-inventory`
- **FR-8**: Evaluate and audit recovery behavior reproducibly → `001-shared-booking-browser-recovery`
- **FR-9**: Present inventory recovery outcomes clearly → `002-agent-assisted-booking-inventory`

Every functional requirement is assigned exactly once.

## Units Overview

### Unit 1: `001-shared-booking-browser-recovery`

**Description**: Own provider-neutral action outcomes, semantic progress detection, evidence-rich
agent turns, step-local recovery policy, caller/role LLM resolution, replay fixtures, and the
existing price-check integration.

**Stories**:

- `001-detect-and-stop-semantic-no-progress`
- `002-reorient-with-evidence-rich-feedback`
- `003-back-every-booking-browser-step-with-guarded-recovery`
- `004-evaluate-recovery-with-replay-fixtures`

**Dependencies**: Existing agentic escalation, production search reliability, coordinator, action
guard, caller-scoped LLM factory, and trace infrastructure.

### Unit 2: `002-agent-assisted-booking-inventory`

**Description**: Apply the shared recovery contract to authenticated account inventory navigation
and typed interpretation while preserving authoritative identity, completeness, reconciliation,
Telegram freshness, and daily LLM accounting.

**Stories**:

- `001-recover-complete-booking-inventory-discovery`
- `002-preserve-completeness-and-safety-under-agent-assistance`
- `003-explain-and-observe-inventory-recovery`

**Dependencies**: Unit 1 plus existing account synchronization core and synchronized interface.

## Unit Dependency Graph

```text
[Existing Agent + Search Journey]
                 |
                 v
[001-shared-booking-browser-recovery]
                 |
                 v
[002-agent-assisted-booking-inventory]
                 |
                 v
[/bookings + /checknow + scheduled synchronization]
```

## Execution Order

1. Build and prove the reusable progress-aware agent contract.
2. Preserve price-check behavior under the hardened loop.
3. Integrate caller-scoped LLM recovery and interpretation into account inventory.
4. Verify completeness, safety, accounting, Telegram, and end-to-end trigger invariants.
