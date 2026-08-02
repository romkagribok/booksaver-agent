---
id: 004-evaluate-recovery-with-replay-fixtures
unit: 001-shared-booking-browser-recovery
intent: 021-booking-browser-llm-recovery
status: complete
priority: must
created: 2026-08-02T18:07:49.000Z
assigned_bolt: 038-shared-booking-browser-recovery
implemented: true
---

# Story: Evaluate Recovery with Replay Fixtures

## User Story

**As a** BookSaver operator
**I want** reproducible agent evaluations based on real failure shapes
**So that** prompts and future model/provider choices are measured rather than guessed

## Acceptance Criteria

- [ ] **Given** the production no-href/new-window incident fixture, **When** offline controller tests
  run, **Then** equivalent clicks are bounded, a screenshot is forced, and the run ends accurately.
- [ ] **Given** account inventory and adversarial safety fixtures, **When** offline tests run, **Then**
  progress, safe give-up, completeness, and prohibited-action invariants are deterministic.
- [ ] **Given** an operator explicitly runs live replay, **When** a curated model profile is selected,
  **Then** ten sanitized runs report success/give-up accuracy, actions, calls, latency, and usage.
- [ ] **Given** ordinary CI or the full default pytest suite, **When** tests run, **Then** no external
  LLM or Booking.com network call is made.
- [ ] **Given** traces or reports are inspected, **When** they are rendered, **Then** they omit raw
  prompts, cookies, keys, full confirmation IDs, and chain-of-thought.

## Technical Notes

- Store synthetic/sanitized observation fixtures, not production session artifacts.
- Keep provider evaluation behind an explicit CLI flag/environment capability.
- Contract is provider-neutral so GitHub issue #3 can reuse it later.

## Dependencies

### Requires

- Stories 001–003 in this unit.

### Enables

- Evidence-based model selection and multi-provider contract testing.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Live key missing | Evaluation refuses clearly without affecting normal BookSaver state |
| Model output is stochastic | Aggregate threshold is measured across ten isolated runs |
| Fixture contains sensitive strings | Validation rejects it before provider use |

## Out of Scope

- Automatically choosing or switching production providers.
