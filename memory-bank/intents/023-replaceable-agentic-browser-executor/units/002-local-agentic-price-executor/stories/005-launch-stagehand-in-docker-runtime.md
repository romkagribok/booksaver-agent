---
id: 005-launch-stagehand-in-docker-runtime
unit: 002-local-agentic-price-executor
intent: 023-replaceable-agentic-browser-executor
status: draft
priority: must
created: 2026-08-25T01:10:13Z
assigned_bolt: 054-local-agentic-price-executor
implemented: false
---

# Story: Launch Stagehand in the Docker Runtime

## User Story

**As a** self-hosting owner
**I want** the local Stagehand browser to launch in BookSaver's production container
**So that** owner-canary checks can use the qualified executor without a CI-only workaround

## Acceptance Criteria

- [ ] Stagehand receives an explicit container-compatible Chromium sandbox setting that matches the
  existing Playwright runtime instead of inferring it from `CI`.
- [ ] Chromium and BookSaver continue to run as the unprivileged container user; no root browser,
  privileged container, host browser service, or broader container capability is introduced.
- [ ] A regression test proves the local Stagehand launch request contains the explicit setting.
- [ ] A production-image smoke launches Stagehand, attaches through loopback CDP, and tears down
  without setting `CI`.
- [ ] Session custody, browser-action guards, destination checks, routing modes, and qualification
  gates remain unchanged.

## Dependencies

- Story 001 and bolt 051's transient local Stagehand runtime.
- The existing Docker image, non-root runtime user, and installed Playwright Chromium.

## Out of Scope

- Privileged containers, Chromium setuid sandbox packaging, managed browsers, caching, selector
  repair, or any change to invited-user promotion.
