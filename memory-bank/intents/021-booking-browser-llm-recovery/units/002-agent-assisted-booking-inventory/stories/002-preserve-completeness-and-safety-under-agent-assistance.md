---
id: 002-preserve-completeness-and-safety-under-agent-assistance
unit: 002-agent-assisted-booking-inventory
intent: 021-booking-browser-llm-recovery
status: complete
priority: must
created: 2026-08-02T18:07:49.000Z
assigned_bolt: 039-agent-assisted-booking-inventory
implemented: true
---

# Story: Preserve Completeness and Safety Under Agent Assistance

## User Story

**As a** BookSaver user
**I want** LLM-assisted discovery to remain fail-closed and read-only
**So that** model adaptation cannot corrupt my reservation truth or perform an account action

## Acceptance Criteria

- [ ] **Given** the model claims all reservations were seen, **When** deterministic scope/pagination
  evidence is incomplete, **Then** the synchronization remains incomplete.
- [ ] **Given** an incomplete assisted run with positive validated observations, **When** it commits,
  **Then** positives may update but unseen reservations remain current and are never marked absent.
- [ ] **Given** missing, conflicting, or guessed remote identity, **When** validation runs, **Then** the
  observation fails closed and does not merge with another reservation.
- [ ] **Given** cancel, modify, change dates, reserve again, payment, checkout, account settings, or
  external-provider controls, **When** a model proposes them, **Then** zero actions execute.
- [ ] **Given** a popup or landed page after an action, **When** its URL is unsafe or external, **Then**
  the run terminates before further observation or interpretation.
- [ ] **Given** account page prices, **When** assisted interpretation occurs, **Then** they remain booked
  baseline facts only and cannot become replacement offers.

## Technical Notes

- Reuse ADR-028 completeness-gated reconciliation unchanged.
- Validate typed candidates through existing value objects and reason-coded eligibility.
- Extend the guard matrix for inventory mutation/account-setting targets and every top-level page.

## Dependencies

### Requires

- `001-recover-complete-booking-inventory-discovery`

### Enables

- Safe production use of inventory recovery.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| All scopes deterministically prove explicit empty | Complete empty inventory is permitted |
| One scope contains ambiguous “no bookings” text | Incomplete, never absence reconciliation |
| LLM returns otherwise valid facts with conflicting lifecycle | Identity ambiguity failure |

## Out of Scope

- Letting model confidence replace deterministic domain validation.
