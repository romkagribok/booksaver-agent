---
stage: test
bolt: 052-agentic-browser-qualification
created: 2026-08-17T04:21:00Z
status: complete-offline
---

# Test Report: Agentic Browser Qualification

## Completed Offline Evidence

- **Focused agentic/guard/session/routing tests**: 148 passed.
- **Repository suite**: 1,691 passed, 55 existing schedule-deprecation warnings.
- **Ruff**: all source and tests passed.
- **Strict mypy**: 124 source files passed.
- **Packaging smoke**: installed Stagehand version is exactly 4.0.1 and the transient Chromium CDP
  session test passed.

## Acceptance Coverage

- All six named DOM-churn dimensions execute without a BookSaver selector change; the three
  non-semantic variants complete only through the guarded computer-use branch.
- Egress lookalikes, Browserbase/OpenAI/remote telemetry, non-HTTPS Anthropic, unsafe paths, popup
  changes, prohibited labels, coordinates, keys, waits, zoom, scrolls, and invented typed values
  fail closed.
- Cookie injection/read-back and transient teardown use a real local Chromium. Session values are
  absent from contracts/repr/logs and provider exception content is redacted. Authenticated success
  also requires two code-owned fixed protected-resource server proofs before refreshed cookies are
  revision-safely returned to encrypted persistence.
- Threshold boundary tests cover check count/span, manual comparison count/correctness, 95% valid
  rate, exact average cost, nearest-rank p95 cost/duration, 20% fallback, every critical violation,
  and explicit owner approval.
- Schema-v16 tests prove content-free columns, active-owner authority, current invitee consent,
  repository-owned promotion evaluation, immediate critical regression, and automatic regression
  after three consecutive eligible failures inside the rollback window.

## Deliberately Pending

The live owner canary has not run. Promotion therefore remains unqualified and `legacy` remains the
default route. Bolt 052 stays in progress until at least 30 authentic owner checks span 14 days, at
least 10 successful observations are manually compared, all quantitative gates pass, and the owner
runs the explicit promotion command.
