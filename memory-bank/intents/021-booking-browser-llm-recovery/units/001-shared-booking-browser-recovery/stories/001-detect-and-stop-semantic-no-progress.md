---
id: 001-detect-and-stop-semantic-no-progress
unit: 001-shared-booking-browser-recovery
intent: 021-booking-browser-llm-recovery
status: complete
priority: must
created: 2026-08-02T18:07:49.000Z
assigned_bolt: 038-shared-booking-browser-recovery
implemented: true
---

# Story: Detect and Stop Semantic No-Progress

## User Story

**As a** BookSaver user
**I want** the browser agent to recognize when its actions are not changing the verified page state
**So that** a changed Booking.com page cannot consume the full budget through repeated ineffective clicks

## Acceptance Criteria

- [ ] **Given** equivalent controls receive different refs, **When** the model repeatedly targets the
  same normalized role/label/href/value, **Then** no more than two executions reach Playwright.
- [ ] **Given** the model alternates equivalent targets while the page remains unchanged, **When**
  semantic progress is evaluated, **Then** the shared no-progress streak continues.
- [ ] **Given** an action returns normally but URL/content/elements and verification remain unchanged,
  **When** its outcome is recorded, **Then** it is classified as no progress.
- [ ] **Given** a material controllable-page change or passed verifier, **When** the outcome is
  evaluated, **Then** the no-progress streak resets or the step succeeds.
- [ ] **Given** an unreachable step, **When** recovery runs, **Then** it terminates within four LLM
  calls and 60 seconds with a coded reason.

## Technical Notes

- Domain-owned semantic target signatures exclude transient refs when semantic metadata is present.
- Page fingerprints are bounded and never persisted as source material.
- A step-local policy nests inside existing `AgentBudget` outer caps.

## Dependencies

### Requires

- Existing agent loop and guarded browser actions.

### Enables

- `002-reorient-with-evidence-rich-feedback`
- `003-back-every-booking-browser-step-with-guarded-recovery`

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Two different cards share the same label | Stable occurrence/safe destination prevents a false collision |
| Action throws after navigation | Post-action observation may still prove progress |
| Screenshot capture fails | Recovery remains bounded and terminates with diagnostic evidence |

## Out of Scope

- Adopting or controlling a newly opened popup page.
