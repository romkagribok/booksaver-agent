---
stage: test
bolt: 038-shared-booking-browser-recovery
created: 2026-08-02T18:40:18Z
status: complete
---

# Test Report: Shared Booking Browser Recovery

## Outcome

The shared recovery controller, browser metadata, provider prompt/factory, configuration,
redacted traces, and replay evaluation are implemented and verified. Deterministic healthy paths
remain model-free. Failed operations receive typed evidence and stop under the configured inner
limits without weakening the existing outer budgets or ActionGuard.

## Coverage

- Semantic no-progress across changed references and alternating equivalent controls.
- Authoritative pre/post verification, material-progress reset, and refused third execution.
- Forced screenshot reorientation and one post-reorientation no-progress stop.
- Four-call and 60-second local limits nested under existing check limits.
- Provider errors, coded give-up, unsafe actions, blocked/external destinations, and popup overflow.
- Sanitized scroll/popup observation metadata and complete browser-context cleanup.
- Versioned Anthropic prompt mapping and explicit active-user/operation factory resolution.
- Backward-compatible configuration defaults and CLI rendering.
- Redacted structured traces that omit refs, labels, values, semantic targets, and provider text.
- Strict packaged replay fixtures and an explicit live-model CLI that never opens a browser or
  reads the database/session vault.

## Verification Evidence

| Gate | Result |
|---|---:|
| Focused domain, controller, provider, browser, trace, config, CLI, replay, and persistence tests | 335 passed |
| Final integrated repository test suite after bolt 039 | 1225 passed |
| Focused Ruff checks during construction | Passed |
| Focused strict mypy checks during construction | Passed |
| Diff whitespace validation | Passed |

The final integrated gate also passed full Ruff, strict mypy across 103 source files, CLI/config
smoke checks, AI-DLC validation, and diff whitespace validation.

## Story Coverage

- **US-122**: Structured progress classification and semantic loop containment.
- **US-123**: Evidence-rich typed context, screenshot reorientation, and accurate termination.
- **US-124**: Reusable generic recovery labels, explicit user/role factory seams, and search
  journey compatibility.
- **US-125**: Privacy-safe replay corpus, metrics, package data, and explicit live evaluation CLI.

## Residual Acceptance

No production model or Booking.com call was made during tests. A future approved VPS acceptance
may run the packaged replay command and real `/bookings`/`/checknow` smoke tests; neither is needed
to establish deterministic repository correctness.
