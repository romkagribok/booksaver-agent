---
id: 001-escalate-sonnet-to-opus-on-quality-failure
unit: 001-adaptive-model-policy
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-13T01:59:59.000Z
assigned_bolt: 041-adaptive-model-policy
implemented: true
---

# Story: Escalate Sonnet to Opus on Quality Failure

## User Story

**As a** BookSaver operator
**I want** ineffective Sonnet 5 recovery to switch automatically to Opus 5
**So that** model quality does not turn a recoverable DOM change into an unexplained failure

## Acceptance Criteria

- [ ] **Given** a browser recovery, interpretation, classification, or diagnostic call is eligible,
  **When** no prior quality failure exists, **Then** the caller-scoped Sonnet 5 profile is selected.
- [ ] **Given** Sonnet produces repeated semantic no-progress, two invalid schemas, unsafe proposals,
  unresolved low confidence, or an unverified exhausted episode, **When** safety/provider/time/cost
  policy still permits work, **Then** Opus 5 receives one bounded structured handoff.
- [ ] **Given** authentication, MFA, captcha, bot wall, prohibited action, provider-wide failure, or
  exhausted budget is already conclusive, **When** routing evaluates escalation, **Then** it stops
  under that exact reason and does not spend an Opus call.
- [ ] **Given** configuration names Fable or an unapproved model in the resilience portfolio, **When**
  configuration loads, **Then** validation fails before the daemon starts browser work.
- [ ] **Given** a personal caller key cannot access Opus, **When** escalation is attempted, **Then**
  BookSaver reports caller-scoped model unavailability and never borrows the owner key.
- [ ] **Given** either model is called, **When** the attempt completes, **Then** the ordered audit
  records role, model, trigger, outcome, calls, tokens, latency, and cost without page content.

## Technical Notes

- Introduce a provider-neutral model portfolio/router around current `AgentBrain` and interpreter
  creation rather than embedding model selection in workflow modules.
- Transfer structured outcomes and bounded observation only; never copy chain-of-thought.
- Preserve a distinct final diagnostic role that cannot execute browser actions.

## Dependencies

### Requires

- Existing provider-neutral LLM ports, Anthropic adapter, caller-scoped client factory, and ADR-030.

### Enables

- US-131 through US-139.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Sonnet model ID unavailable but Opus is accessible | Use the explicit eligible provider/model-unavailable policy; do not silently change provider |
| Sonnet proposes a prohibited action | Reject action, record quality/safety result, and escalate only if the step remains safely diagnosable |
| Opus returns invalid schema | Terminate `invalid_provider_response` with ordered attempt evidence |
| Caller is removed during handoff | Stop before Opus and release all browser/coordinator resources |

## Out of Scope

- Fable or cross-provider failover.
- Allowing Opus to override ActionGuard, domain verifiers, or caller isolation.
