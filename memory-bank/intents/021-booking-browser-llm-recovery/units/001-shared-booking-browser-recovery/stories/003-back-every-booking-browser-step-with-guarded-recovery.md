---
id: 003-back-every-booking-browser-step-with-guarded-recovery
unit: 001-shared-booking-browser-recovery
intent: 021-booking-browser-llm-recovery
status: complete
priority: must
created: 2026-08-02T18:07:49.000Z
assigned_bolt: 038-shared-booking-browser-recovery
implemented: true
---

# Story: Back Every Booking Browser Step with Guarded Recovery

## User Story

**As a** BookSaver user
**I want** every automated read-only Booking.com journey to share the same reliable fallback
**So that** layout changes do not create separate brittle recovery implementations

## Acceptance Criteria

- [ ] **Given** a named search-journey step fails, **When** the failure is recoverable, **Then** the
  hardened shared controller receives its step-specific goal and verifier.
- [ ] **Given** a future automated journey registers a recovery step, **When** it fails, **Then** it
  can reuse the same controller without provider-specific code in the journey.
- [ ] **Given** a human login or credential/MFA page, **When** browser work occurs, **Then** no LLM
  observation, screenshot, or action is created.
- [ ] **Given** a caller-scoped operation, **When** an agent brain is resolved, **Then** the explicit
  user and operation role select the key/model and usage boundary without cross-user fallback.
- [ ] **Given** daily LLM allowance is exhausted, **When** a scripted journey needs recovery, **Then**
  it fails visibly in deterministic-only mode and records zero uncounted provider calls.

## Technical Notes

- Evolve the factory from booking-only brain resolution to explicit user/role resolution.
- Preserve booking-based compatibility wrappers where they make migration safer.
- Unit 2 supplies the inventory-specific journey and interpreter.

## Dependencies

### Requires

- `001-detect-and-stop-semantic-no-progress`
- `002-reorient-with-evidence-rich-feedback`

### Enables

- Unit 2 account inventory recovery.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Caller is revoked before work | No browser or LLM work starts |
| Owner-funded invited user | Existing permitted owner-key policy remains bounded by that user's usage |
| No configured key | Deterministic-only behavior, no crash |

## Out of Scope

- New providers or silent provider fallback.
