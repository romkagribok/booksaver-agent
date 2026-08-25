---
unit: 002-local-agentic-price-executor
intent: 023-replaceable-agentic-browser-executor
phase: inception
status: complete
created: "2026-08-16T19:18:41Z"
updated: "2026-08-25T01:10:13Z"
unit_type: backend
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: Local Agentic Price Executor

## Purpose

Replace complete price-check navigation and rate perception with a local Stagehand semantic path and
one guarded Anthropic computer-use fallback on the same transient Chromium.

## Scope

### In Scope

- Pinned Stagehand v4 async runner and Chromium executable reuse.
- Observe/guard/replay navigation and typed rate extraction.
- Closed computer-use loop with generic hit testing and destination guards.
- Content-safe metrics, telemetry confinement, cleanup, and `/connect` disclosure.

### Out of Scope

- Domain equivalence/savings decisions (unit 001).
- Managed browsers, custom caches, selector learning, code repair, or local models.
- Inventory synchronization and `/connect` authentication authority.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-4 | Local Stagehand semantic execution | Must |
| FR-5 | Guarded Anthropic computer-use fallback | Must |
| FR-8 | Privacy-safe disclosure and observability | Must |

## Domain Concepts

- **SemanticActionPreview**: Stagehand observation translated to a guardable action proposal.
- **ComputerUseActionRequest**: Closed Sonnet action vocabulary and screenshot-bound turn.
- **ActionHitTest**: Browser-owned element/destination facts for coordinate clicks.
- **TypedPriceSubmission**: Final structured observation or closed terminal outcome.

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 5 |
| Must Have | 5 |
| Should Have | 0 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-147 | Run Stagehand in a transient local browser | Must | Complete |
| US-148 | Guard semantic navigation and extract typed rates | Must | Complete |
| US-149 | Recover visually through guarded computer use | Must | Complete |
| US-150 | Confine content and disclose Anthropic processing | Must | Complete |
| US-155 | Launch Stagehand in the Docker runtime | Must | Complete |

## Dependencies

- Unit 001 contracts and routing.
- Stagehand 4.0.1, Anthropic SDK, installed Chromium, Booking.com, and existing global browser lease.
- Existing non-root Docker image and Playwright's container-compatible Chromium launch behavior.

## Constraints

- One in-process async runner; no sidecar or managed browser.
- One fallback episode and six computer-use actions maximum.
- Stagehand external telemetry is disabled or loopback-only.
- Docker compatibility must be explicit at the Stagehand launch boundary and must not depend on the
  generic `CI` environment variable.

## Success Criteria

- [ ] Stagehand and computer use share the same browser and never receive cookie values directly.
- [ ] Every action proposal is code-guarded before execution and destination-checked after execution.
- [ ] Typed terminal outcomes cover signed-out, MFA, captcha, bot wall, unavailable, provider failure,
  budget, and timeout.
- [ ] Transient profile cleanup is deterministic.

## Bolt Suggestions

- `051-local-agentic-price-executor`: US-147 through US-150 after bolt 050.
- `054-local-agentic-price-executor`: US-155 production-container correction after bolt 051.
