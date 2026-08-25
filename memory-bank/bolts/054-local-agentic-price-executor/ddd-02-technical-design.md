---
stage: design
bolt: 054-local-agentic-price-executor
created: 2026-08-25T01:12:00Z
status: complete
---

# Technical Design: Container-Compatible Stagehand Launch

## Architecture Pattern

Preserve the existing in-process adapter from ADR-037. Make BookSaver's production browser launch
contract explicit at the single Stagehand `local_browser.launch` boundary instead of relying on the
library's generic environment inference.

## Layer Structure

- **Infrastructure browser adapter**: pass `chromium_sandbox=False` while retaining the installed
  executable, loopback CDP, unique profile directory, headless mode, and deterministic teardown.
- **Domain/application layers**: unchanged. Executor contracts, observation validation, action
  guards, cost limits, routing, and qualification remain authoritative and provider-neutral.
- **Container packaging**: continue running as the existing non-root `booksaver` user. Correct the
  image documentation so it does not claim a Chromium sandbox property contradicted by the actual
  Playwright launch behavior.

## API and Data Design

No public API, configuration, environment variable, schema, persistence, or executor-result change.
The compatibility setting is an adapter implementation detail and is deliberately not exposed as
an operator toggle.

## Security Design

- Do not set `CI=1`; a generic environment flag has unrelated semantics and can affect other tools.
- Do not run Chromium or BookSaver as root.
- Do not enable privileged mode, host networking, new Linux capabilities, or a remote browser.
- Preserve loopback-only CDP and telemetry confinement, transient profiles, action hit-testing,
  destination validation, and prohibited-action enforcement.
- Treat the container boundary plus BookSaver's code guards as the runtime controls; do not describe
  Chromium's disabled internal sandbox as an active protection.

## Verification Design

1. A unit regression replaces the Stagehand and Playwright launch seams with fakes, invokes
   `LocalStagehandRuntime.launch`, and asserts `chromium_sandbox` is exactly `False` alongside the
   existing executable and lifecycle arguments.
2. Existing focused browser-executor, session-bootstrap, packaging, lint, typing, and repository
   tests must pass.
3. The exact candidate Docker image must launch Stagehand without `CI`, attach to loopback CDP,
   reach the local telemetry sink, and close without leaked Chromium processes.
4. The existing owner-canary qualification ledger remains empty until an authentic owner check runs;
   this deployment smoke is release evidence only.

## Rollback

The code change is one explicit launch argument. Rollback remains the preserved pre-deployment image,
configuration, and SQLite copy. No data migration is introduced by this bolt; schema v16 remains the
already-approved agentic qualification migration applied during deployment.
