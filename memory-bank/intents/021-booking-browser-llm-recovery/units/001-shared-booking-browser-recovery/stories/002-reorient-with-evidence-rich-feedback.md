---
id: 002-reorient-with-evidence-rich-feedback
unit: 001-shared-booking-browser-recovery
intent: 021-booking-browser-llm-recovery
status: complete
priority: must
created: 2026-08-02T18:07:49.000Z
assigned_bolt: 038-shared-booking-browser-recovery
implemented: true
---

# Story: Reorient with Evidence-Rich Feedback

## User Story

**As a** BookSaver operator
**I want** the LLM to receive explicit action outcomes and one fresh visual reorientation
**So that** model behavior is informed by verified evidence instead of misleading “click succeeded” feedback

## Acceptance Criteria

- [ ] **Given** any proposed action, **When** the next turn is created, **Then** it includes structured
  execution, state-change, popup, verifier, and no-progress evidence.
- [ ] **Given** two no-progress outcomes, **When** another decision is requested, **Then** the current
  screenshot is attached automatically even if neither action raised.
- [ ] **Given** a same-host popup appears while the controllable page stays unchanged, **When** feedback
  is rendered, **Then** the model is told the popup is present but unavailable to current tools.
- [ ] **Given** the visual recovery action still makes no progress, **When** the controller evaluates
  it, **Then** recovery ends with `agent_no_progress` or `missing_browser_capability`.
- [ ] **Given** a provider/network/schema error, **When** the brain call fails, **Then** it becomes a
  distinct redacted LLM failure rather than an uncaught worker exception.

## Technical Notes

- Replace free-form history at the provider boundary with typed turn context.
- Provider adapters serialize context but do not own progress or safety decisions.
- `give_up` accepts a normalized reason code plus bounded explanation.

## Dependencies

### Requires

- `001-detect-and-stop-semantic-no-progress`

### Enables

- Shared search and inventory recovery.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Popup URL is blocked or external | Fail closed before another model turn |
| Model changes refs after feedback | Semantic outcome history remains meaningful |
| Provider emits no valid tool call | Controlled provider/model failure, no arbitrary action |

## Out of Scope

- Persisting chain-of-thought or full provider messages.
