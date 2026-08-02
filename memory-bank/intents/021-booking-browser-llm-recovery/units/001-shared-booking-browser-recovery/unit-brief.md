---
unit: 001-shared-booking-browser-recovery
intent: 021-booking-browser-llm-recovery
phase: inception
status: complete
created: 2026-08-02T18:07:49.000Z
updated: 2026-08-02T18:07:49.000Z
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: Shared Booking Browser Recovery

## Purpose

Provide one provider-neutral, progress-aware LLM recovery controller for every automated read-only
Booking.com browser journey. The unit makes browser outcomes truthful, prevents semantic loops,
applies tighter per-step bounds, preserves existing guards, and creates reusable evaluation fixtures.

## Scope

### In Scope

- Structured action outcome and page-state progress signals.
- Semantic target identity independent of element refs.
- Evidence-rich agent turn context and coded stop reasons.
- Screenshot escalation after successful-but-unverified no-progress actions.
- Step-local call/time limits nested inside existing total budgets.
- Caller/operation-scoped LLM factory and usage accounting contracts.
- Price-search integration and sanitized replay evaluation.

### Out of Scope

- Account inventory traversal and reconciliation, owned by Unit 2.
- Popup adoption or deterministic Booking.com selector repairs.
- Provider additions, arbitrary URLs/selectors/JS, or human login control.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Report verified browser-action outcomes | Must |
| FR-2 | Detect semantic no-progress and terminate accurately | Must |
| FR-3 | Use step-specific, evidence-rich LLM recovery | Must |
| FR-4 | Back every automated Booking.com browser journey with guarded recovery | Must |
| FR-5 | Resolve LLM capability and usage by caller and operation | Must |
| FR-8 | Evaluate and audit recovery behavior reproducibly | Must |

## Domain Concepts

- **PageState**: Bounded fingerprintable state before or after an action.
- **SemanticTarget**: Stable meaning of an action target across volatile refs.
- **ActionOutcome**: Execution, progress, popup, verification, and safe error evidence.
- **AgentTurnContext**: Goal, observation, structured history, and remaining policy.
- **RecoveryPolicy**: Step-local no-progress, call, screenshot, and time bounds.
- **AgentStopReason**: Normalized reason for controlled termination.

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 4 |
| Must Have | 4 |
| Should Have | 0 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-122 | Detect and stop semantic no-progress | Must | Ready |
| US-123 | Reorient with evidence-rich feedback | Must | Ready |
| US-124 | Back every booking browser step with guarded recovery | Must | Ready |
| US-125 | Evaluate recovery with replay fixtures | Must | Ready |

## Dependencies

- Existing `BrowserAgent`, `AgentBrain`, `InteractiveBrowser`, `AgentBudget`, action guard, trace,
  caller-scoped key factory, and CheckCoordinator usage counters.
- ADR-015, ADR-016, ADR-017, ADR-020, and ADR-021.

## Technical Context

- Extend explicit domain/application contracts; keep provider rendering in the Anthropic adapter.
- Prefer additive defaulted observation fields to reduce fixture churn.
- Persist only outcome flags and safe summaries, never fingerprint source text or hidden reasoning.
- Keep outer check budgets; add a tighter recovery policy rather than replacing them.

## Success Criteria

- [ ] Changing refs and alternating equivalent targets cannot evade loop control.
- [ ] Successful-but-unchanged actions trigger screenshot escalation and bounded termination.
- [ ] Current search recovery remains guarded and verifiable.
- [ ] Provider failures become distinct redacted results.
- [ ] Offline fixtures and opt-in replay make model behavior measurable.
- [ ] Focused and full repository quality gates pass.

## Bolt Suggestion

- `038-shared-booking-browser-recovery`: one DDD bolt covering all four stories and ADR-030.
