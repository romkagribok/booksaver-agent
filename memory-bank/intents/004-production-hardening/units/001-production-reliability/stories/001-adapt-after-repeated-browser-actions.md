---
id: 001-adapt-after-repeated-browser-actions
unit: 001-production-reliability
intent: 004-production-hardening
status: ready
priority: must
created: 2026-07-18T17:48:48Z
assigned_bolt: 013-production-reliability
implemented: false
---

# Story: Adapt After Repeated Browser Actions

**Global story ID**: US-037

## User Story

**As a** BookSaver operator
**I want** the screenshot-aware browser agent to recognize when one action is not changing the page
**So that** it tries a materially different recovery instead of wasting time and budget in a loop

## Acceptance Criteria

- [ ] **Given** a journey step has entered visual recovery, **When** the agent decides its next
  action, **Then** its observation includes the current screenshot.
- [ ] **Given** the same successful-but-unverified action has executed twice, **When** the model
  proposes it again, **Then** the adapter is not called and an `agent_blocked` trace explains that a
  different action is required.
- [ ] **Given** a duplicate action was refused, **When** recovery continues, **Then** the model gets
  a fresh screenshot and the refusal in its tool history.
- [ ] **Given** five identical proposals occur without verified progress, **When** the hard loop
  limit is reached, **Then** the result is `AGENT_GAVE_UP`.
- [ ] **Given** the model proposes a forbidden or over-budget action, **When** it is evaluated, **Then**
  existing guard and budget behavior remains terminal.

## Technical Notes

- Normalize proposals using the existing action signature used for loop detection.
- Separate proposal count from browser-execution count so refused duplicates do not reach Playwright.
- Reuse existing screenshot-tier and trace seams; no new agent framework or action type.

## Dependencies

### Requires

- Intent 002, US-020 through US-022 (completed browser-agent takeover, guard/caps, traces).

### Enables

- 002-continue-fill-search-from-trusted-data.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Same action type with different element reference | Treat as a different proposal and allow guard/adapter evaluation |
| Adapter reports action failure | Existing failure/recovery behavior applies; do not classify it as successful duplicate progress |
| Screenshot unavailable | Preserve existing text-tier behavior and bounded failure; never weaken the guard |

## Out of Scope

- Teaching the model Booking.com's current calendar DOM.
- Raising the existing hard call, token, or cost limits.
- Allowing reserve, checkout, payment, or cancellation actions.
