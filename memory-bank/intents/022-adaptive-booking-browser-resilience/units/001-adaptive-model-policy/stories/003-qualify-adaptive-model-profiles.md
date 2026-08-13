---
id: 003-qualify-adaptive-model-profiles
unit: 001-adaptive-model-policy
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-13T01:59:59.000Z
assigned_bolt: 041-adaptive-model-policy
implemented: true
---

# Story: Qualify Adaptive Model Profiles

## User Story

**As a** BookSaver operator
**I want** Sonnet and Opus recovery behavior measured against real failure shapes
**So that** a weak model or prompt is detected before it becomes production policy

## Acceptance Criteria

- [ ] **Given** the sanitized fixture catalog, **When** offline tests run, **Then** fake models cover
  every registered DOM step, routing trigger, safety stop, and cost admission deterministically.
- [ ] **Given** an explicit live-replay command, **When** Sonnet/Opus profiles run without opening
  Booking.com, **Then** ten runs per fixture report completion/diagnosis accuracy, schema validity,
  safety, escalation, calls, actions, latency, tokens, and estimated cost.
- [ ] **Given** a solvable or unreachable fixture, **When** qualification completes, **Then** at least
  nine of ten runs recover correctly or diagnose accurately and every safety fixture executes zero
  prohibited actions.
- [ ] **Given** a model or prompt misses the gate, **When** production config selects it, **Then**
  startup/release validation rejects it unless an owner override with local audit is supplied.
- [ ] **Given** replay input/output is inspected, **When** reports and logs are generated, **Then**
  they contain no session, reservation, property, URL-query, prompt-secret, or page-account data.

## Technical Notes

- Extend the existing `ReplayRunner` and sanitized intent-021 fixtures.
- Include the production-shaped auth disagreement and terminal reason propagation cases.
- Keep live model replay opt-in and outside the ordinary test suite.

## Dependencies

### Requires

- US-130 and US-131 plus existing replay infrastructure.

### Enables

- Release qualification for bolts 042 and 043.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Anthropic unavailable during live replay | Report provider unavailability; do not pass the profile |
| Replay would exceed explicit evaluation budget | Stop with cost reason and partial report |
| Models disagree on maintenance need | Report disagreement and preserve deterministic safety expectation |

## Out of Scope

- Live Booking.com automation or production user evidence in replay.
- Automatic production promotion based only on a replay score.
