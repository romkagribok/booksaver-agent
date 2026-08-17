---
id: 004-confine-content-and-disclose-processing
unit: 002-local-agentic-price-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: '2026-08-16T19:18:41Z'
assigned_bolt: 051-local-agentic-price-executor
implemented: true
---

# Story: Confine Content and Disclose Anthropic Processing

## User Story

**As an** invited BookSaver user
**I want** explicit disclosure and content-minimizing execution
**So that** I understand and control when visible authenticated page data reaches Anthropic

## Acceptance Criteria

- [x] External Stagehand telemetry/log export is disabled or loopback-only and egress is allowlisted.
- [x] Persistence contains only redacted metrics/failure codes, never page content or reasoning.
- [x] `/connect` presents a versioned disclosure and records acknowledgement without changing server
  authentication verification.
- [x] Invitees without current acknowledgement remain on legacy routing.

## Dependencies

- US-145, US-146, and existing invite/user/session boundaries.

## Out of Scope

- Consent for unrelated providers or a BookSaver cloud service.
