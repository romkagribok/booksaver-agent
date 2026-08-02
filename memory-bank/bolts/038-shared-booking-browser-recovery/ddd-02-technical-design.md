---
stage: technical-design
bolt: 038-shared-booking-browser-recovery
created: 2026-08-02T18:16:29Z
status: complete
---

# Technical Design: Shared Booking Browser Recovery

## Architecture Pattern

Extend the existing hexagonal browser-agent boundary with domain-owned recovery state and
provider-neutral turn context. Keep deterministic journeys as primary adapters, `BrowserAgent` as
the application/domain orchestrator, Playwright as the driven browser adapter, and Anthropic as one
provider adapter. No agent framework, asynchronous browser, or persistence schema is introduced.

## Layer Structure

```text
Journey step / verifier
        |
        v
RecoveryController (BrowserAgent)
        |
        +--> ProgressClassifier + SemanticLoopGuard + RecoveryPolicy
        |
        +--> AgentBrain port --> AnthropicAgentBrain
        |
        +--> InteractiveBrowser port --> PlaywrightInteractiveBrowser
        |
        +--> TraceRecorder / caller usage accounting
```

## Domain Changes

### `src/booksaver/domain/agent.py`

- Add `AgentStopReason` enum.
- Add immutable `RecoveryPolicy` with validated defaults:
  - four LLM calls per step;
  - 60 seconds per step;
  - screenshot after two no-progress outcomes;
  - two executions per semantic target;
  - one post-reorientation no-progress outcome.
- Add `PageState`, `SemanticTarget`, `ProgressEvidence`, `ActionOutcome`, and `AgentTurnContext`.
- Extend `Observation` with defaulted bounded `scroll_y` and sanitized top-level page metadata so
  existing fixture construction remains source-compatible.
- Extend `AgentAction` with optional normalized stop reason while retaining `value` as the bounded
  explanation.
- Add pure normalization/fingerprint/progress helpers with deterministic tests.
- Extend `AgentSettings` with validated recovery-policy settings while preserving existing config
  compatibility and outer budget behavior.

## Application Ports

### `src/booksaver/application/ports.py`

- Change `AgentBrain.decide` to accept one `AgentTurnContext` rather than separate goal,
  observation, and free-form history.
- Extend the LLM factory contract with explicit user/role resolution:
  - `agent_brain_for_user(user_id, role)`;
  - keep `agent_brain_for_booking(booking)` as a compatibility wrapper.
- Keep `InteractiveBrowser.act` bounded and ref-addressed. The controller computes outcomes from
  before/after observations, so browser adapters do not decide progress.

## Recovery Controller

### `src/booksaver/monitor/browser_agent.py`

Replace the current raw-ref streak/free-form loop with this sequence:

1. Check outer and step-local time/call limits.
2. Run the authoritative verifier once before the first model call.
3. Capture the current observation and page state.
4. Build typed `AgentTurnContext`; force screenshot when policy requests reorientation.
5. Invoke the brain, normalizing provider exceptions to a distinct LLM error result.
6. Validate `give_up`, screenshot request, current ref, and adapter-level ActionGuard.
7. Build `SemanticTarget`; refuse execution when its count exceeds policy.
8. Execute the action. Capture any sanitized exception but continue to a post-action observation.
9. Check all observed top-level URLs against blocked/external destination rules.
10. Run the verifier and classify progress from before/after state plus verification.
11. Record `ActionOutcome` in trace and structured history.
12. Reset counters on material controllable progress; otherwise escalate/terminate per policy.

An uncontrollable same-host popup is recorded as a missing capability and does not reset progress.
The controller does not adopt the popup in this bolt.

## Browser Adapter

### `src/booksaver/infrastructure/browser/playwright_adapter.py`

- `observe()` adds bounded scroll position and sanitized top-level page destinations/count.
- Sanitize destinations to scheme/host/path and allowlisted non-sensitive query names; never expose
  tracking/session/confirmation values.
- After every action, BrowserAgent's fresh `observe()` sees newly opened pages even though `_page`
  remains the controllable page.
- Safety checks cover all top-level pages, including popups, not only `_page.url`.
- Cleanup continues to close the context and every page on all terminal outcomes.
- Element semantic metadata uses accessible role/label/href and a stable visible occurrence index.

## Provider Adapter and Prompt Contract

### `src/booksaver/infrastructure/llm/anthropic_adapter.py`

- Replace the hotel-search-only system prompt with one-step, read-only Booking.com recovery policy.
- Add a versioned prompt identifier.
- Render `AgentTurnContext` into:
  - step goal and authoritative verification condition;
  - current page observation;
  - structured prior outcomes;
  - whether execution/progress/popup/verification changed;
  - remaining local calls/time and forced screenshot state;
  - explicit instruction that ref changes do not create a new semantic target.
- Change `give_up` schema to require a reason-code enum and bounded explanation.
- Keep one forced tool call per turn and map malformed/unknown calls to controlled failure.
- Do not persist provider response text or chain-of-thought.

## Client Factory and Accounting Seam

### `src/booksaver/infrastructure/llm/client_factory.py`

- Resolve keys from an explicit active user for a declared role (`navigation_agent` initially).
- Preserve the current booking wrapper by delegating to its booking owner.
- Expose provider/model/role metadata for redacted audit.
- Unit 2 will use this explicit user seam before any booking aggregate exists.

The coordinator remains authoritative for actual-call accounting. A counting brain wrapper reports
each provider call exactly once to the existing per-user daily counter. No allowance means no brain.

## Configuration

Extend `[agent]` with defaults:

```toml
max_recovery_calls_per_step = 4
recovery_timeout_seconds = 60
screenshot_after_no_progress = 2
max_semantic_action_executions = 2
```

All remain subordinate to `max_steps`, `max_llm_calls`, and `check_timeout_seconds`. Generated and
example config, validation, `config show`, README, and runbook explain the nested limits.

## Trace and Failure Semantics

- Add `agent_outcome` trace events with execution/progress flags, semantic target summary, popup
  flag, verifier result, and counters.
- Add distinct failure categories/codes for `agent_no_progress` and `llm_error`; existing
  `agent_gave_up`, `blocked_action`, and `budget_exceeded` remain.
- Persist only safe summaries; never persist raw PageState inputs/digests that could be correlated
  back to sensitive page content.
- Existing check-trace JSON storage is additive and needs no schema migration.

## Replay Evaluation

### Offline

- Add sequenced fake observations/outcomes and capturing fake brain contexts.
- Add sanitized fixtures representing:
  - the no-href, target-blank production incident;
  - changing refs and alternating equivalent targets;
  - progress reset;
  - provider failure;
  - adversarial mutation/external destinations.
- Default unit/integration tests make no external calls.

### Opt-in live-model replay

- Add a CLI command hidden from ordinary daemon flows that accepts an approved fixture/profile and
  run count.
- It invokes the configured brain against a deterministic simulated browser only; it never opens
  Booking.com or reads the production database/session vault.
- Validate fixture redaction before any provider call.
- Report aggregate accuracy, actions, calls, latency, and usage; do not print prompt bodies.

## Security Design

- ActionGuard remains adapter/controller enforced and provider-independent.
- All top-level destinations are checked after actions.
- Human authentication pages are classified non-recoverable before screenshot/prompt creation.
- Provider-visible evidence is bounded and caller-scoped.
- No arbitrary URL, selector, JavaScript, coordinate, or model-created tool is introduced.

## NFR Implementation

- Step-local monotonic clock and call counters enforce four calls/60 seconds.
- Local fingerprints use bounded normalized data and standard-library hashing.
- Additive defaulted fields preserve existing test/construction compatibility.
- Focused loop, prompt, guard, adapter, config, factory, replay, and regression tests precede the
  full repository gate.

## Compatibility and Migration

- Existing `[agent]` config remains valid and receives defaults.
- Existing `agent_brain_for_booking` callers remain supported.
- Existing trace readers ignore new event kinds naturally.
- The search journey retains its current deterministic steps and verifiers; only recovery control
  semantics change.
- ADR-030 explicitly amends ADR-015's meaning of failed action, ADR-016's provider boundary, and
  ADR-017's budget hierarchy.

## Story Coverage

- US-122: domain progress types, loop guard, policy, controller sequence.
- US-123: structured turn context, prompt, screenshot, popup/provider outcome handling.
- US-124: reusable step/factory/accounting seams and search compatibility.
- US-125: trace extensions, sanitized fixtures, offline and opt-in replay evaluation.
