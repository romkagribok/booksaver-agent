---
id: 001-register-every-dom-sensitive-browser-step
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-13T01:59:59.000Z
assigned_bolt: 042-dom-resilient-browser-workflows
implemented: true
---

# Story: Register Every DOM-Sensitive Browser Step

## User Story

**As a** BookSaver maintainer
**I want** every DOM-dependent browser postcondition declared in one coverage contract
**So that** a known failure terminates cheaply and a genuinely ambiguous selector change cannot
bypass adaptive recovery and reason mapping

## Acceptance Criteria

- [ ] **Given** current browser journeys, **When** the registry is inspected, **Then** it includes
  remote authentication/session validation, inventory entry/readiness/scopes/pagination/details/
  extraction, search form/property/context/currency/room-rate work, snapshot, and offer extraction.
- [ ] **Given** a registered step, **When** deterministic verification fails, **Then** its definition
  names allowed actions, protected states, semantic verifier/interpreter schema, recovery policy,
  and all terminal mappings.
- [ ] **Given** current evidence maps conclusively to a known reason such as `/connect` required,
  captcha, blocked destination, observation failure, provider failure, or budget limit, **When** the
  step terminates, **Then** it uses that exact mapping with zero LLM calls.
- [ ] **Given** a future DOM-sensitive step is added without fallback or terminal mapping, **When**
  the structural coverage test runs, **Then** it fails with the missing journey and step.
- [ ] **Given** a deterministic business rejection or infrastructure state is not caused by DOM,
  **When** it is registered as non-recoverable, **Then** it retains its exact reason without an
  unnecessary model call.
- [ ] **Given** a healthy deterministic postcondition, **When** the job runs, **Then** the registry
  adds no provider call or behavior change.

## Technical Notes

- Prefer explicit `DomStepDefinition` data close to application workflows over reflection.
- Use one shared controller contract while keeping step-specific verifier/capability policy.
- Production uses `BookingComSearchMonitor`; legacy monitor coverage must not create false confidence.

## Dependencies

### Requires

- Unit 1 and intent 021 recovery contracts.

### Enables

- US-134, US-135, and US-136.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Step has no safe model action but can be diagnosed | Register diagnosis-only fallback |
| Observation cannot be captured | Map to explicit observation-unavailable reason |
| Same semantic step has inventory/search variants | Separate definitions with shared typed policy |

## Out of Scope

- Automatically discovering arbitrary browser code paths at runtime.
- Treating deterministic domain decisions as DOM steps.
