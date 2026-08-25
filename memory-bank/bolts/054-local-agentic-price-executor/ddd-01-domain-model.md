---
stage: model
bolt: 054-local-agentic-price-executor
created: 2026-08-25T01:10:13Z
status: complete
---

# Static Domain Model: Container-Compatible Stagehand Launch

## Bounded Context

The **Local Browser Runtime** context turns BookSaver's trusted transient-session lease into one
unprivileged, local Chromium process that Stagehand can attach to over loopback CDP. This correction
changes only process launch compatibility. It does not change what the executor may observe, which
actions it may request, what BookSaver executes, or which users may receive agentic routing.

## Entities

### TransientBrowserProcess

- **Identity**: one executor job and its unique temporary profile.
- **Properties**: installed Chromium executable, loopback CDP endpoint, headless mode, process user,
  container-compatible sandbox mode, and lifecycle state.
- **Rules**:
  - The process runs as BookSaver's unprivileged container user.
  - The profile and process are destroyed after every terminal outcome.
  - Browser attachment is loopback-only and remains within the existing global browser lease.

### StagehandAttachment

- **Identity**: one attachment to the transient process.
- **Properties**: pinned Stagehand version, CDP endpoint, loopback telemetry endpoint, and model
  endpoint policy.
- **Rules**:
  - The attachment never receives cookie values as model input.
  - Existing action, destination, budget, and terminal-outcome guards remain authoritative.

## Value Objects

### ChromiumLaunchPolicy

- **Values**: executable path, headless setting, loopback port, temporary profile ownership, and an
  explicit sandbox setting.
- **Constraints**:
  - The sandbox setting is passed directly to the Stagehand launcher and never inferred from `CI`.
  - The setting matches the established Playwright behavior in the same Docker image.
  - Compatibility does not authorize root execution, privileged containers, or new capabilities.

### ExactImageSmokeResult

- **Values**: image revision, launch success, CDP attachment success, teardown success, and whether
  `CI` was absent.
- **Constraints**: the smoke contains no authenticated page content, cookies, screenshots, or model
  calls and cannot count as owner-canary qualification evidence.

## Aggregate

### LocalStagehandRuntime

`LocalStagehandRuntime` owns one `TransientBrowserProcess` and at most one
`StagehandAttachment`. Its invariant is that a successful launch is both container-compatible and
bounded by the accepted ADR-037 security model. Teardown is mandatory whether launch, attachment,
semantic execution, computer use, or cancellation terminates the job.

## Domain Events

- **TransientBrowserLaunched**: emitted internally after the process exposes loopback CDP.
- **StagehandAttached**: emitted internally after the pinned harness attaches to the same process.
- **TransientBrowserDestroyed**: emitted internally after all local clients and the process close.

These are conceptual lifecycle events; this correction adds no persisted event stream.

## Domain Services

- **LaunchPolicyFactory**: supplies the explicit container-compatible launch setting with no ambient
  `CI` dependency.
- **ExactImageSmoke**: proves launch, attachment, and teardown in the built image before promotion.

## Repository Interfaces

None. Launch policy and smoke evidence are runtime/release concerns and must not add persistent
content or browser state.

## Ubiquitous Language

- **Container-compatible sandbox mode**: the Chromium command-line mode already required by the
  existing Playwright Docker runtime; it is distinct from running BookSaver as root or making the
  container privileged.
- **Ambient CI inference**: a library choosing browser security flags from the generic `CI`
  environment variable instead of BookSaver specifying its production launch contract.
- **Exact-image smoke**: a content-free lifecycle test against the precise image proposed for
  deployment.
