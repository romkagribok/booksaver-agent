---
id: 001-prove-dom-resilience-and-privacy-boundaries
unit: 003-agentic-browser-qualification
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-08-16T19:18:41Z
assigned_bolt: 052-agentic-browser-qualification
implemented: true
---

# Story: Prove DOM Resilience and Privacy Boundaries

## User Story

**As a** deployment owner
**I want** adversarial offline qualification
**So that** live canarying starts only after safety and privacy are mechanically demonstrated

## Acceptance Criteria

- [x] Fixtures vary classes, test IDs, nesting, overlays, iframe/shadow placement, and accessibility.
- [x] A non-semantic visual fixture completes only through guarded computer use.
- [x] Signed-out, MFA, captcha, bot wall, unavailable, provider failure, and timeout are typed outcomes.
- [x] Tests cover session injection/read-back, teardown, same-browser handoff, egress allowlisting,
  prohibited actions, and absence of sensitive material in prompts/results/logs/traces.

## Dependencies

- Units 001 and 002.

## Out of Scope

- Claiming live Booking reliability from fixtures alone.
