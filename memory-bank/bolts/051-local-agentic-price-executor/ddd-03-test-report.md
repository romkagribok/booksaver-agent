---
stage: test
bolt: 051-local-agentic-price-executor
created: 2026-08-17T04:30:00Z
status: complete
---

# Test Report: Local Agentic Price Executor

## Summary

- **Focused agentic/guard/session/routing tests**: 148 passed.
- **Repository suite**: 1,691 passed, 55 existing schedule-deprecation warnings.
- **Ruff**: all source and tests passed.
- **Strict mypy**: 124 source files passed.
- **Transient browser smoke**: Stagehand 4.0.1 launched the installed Chromium, accepted a
  code-owned CDP cookie injection, permitted read-back through a separate local CDP client, and
  destroyed the browser on exit. Model-authentication claims cannot produce a success unless two
  fixed protected-resource server probes also qualify the refreshed local session.

## Acceptance Criteria Validation

- **US-147**: Stagehand 4.0.1 is exactly pinned, runs in process on the installed Chromium through
  a dedicated async runner, receives an already-injected transient browser, and always closes it.
- **US-148**: Semantic navigation is `observe -> generic inspection/guard -> exact replay`; typed
  extraction returns offers without equivalence or savings claims. No Booking.com selector is
  owned by the agentic BookSaver path.
- **US-149**: A single same-browser Sonnet 5 computer-use episode exposes only click, scroll, type,
  key, wait, and region-based screenshot zoom using Anthropic's `computer_20251124` contract.
  Clicks are hit-tested, typed values must exactly match trusted query values, all actions are
  guarded before and after execution, and only typed submission/terminal tools end the episode.
- **US-150**: Stagehand traces terminate at a loopback discard sink, logging is disabled, provider
  exception content is not logged, screenshots remain in memory, cross-run caching/self-healing is
  off, and invited users receive a versioned disclosure gate before `/connect` continues.

## Limit and Failure Validation

- Semantic and visual calls share persisted USD 1 job/USD 10 UTC-day admission, including prior
  inventory calls in the same coordinator job; successful, failed, cancelled, and conservatively
  billed calls reconcile into exact redacted usage.
- The 15 total-action, six computer-action, and 180-second ceilings fail closed. A sixth visual
  action may be followed only by a typed terminal submission, never a seventh browser action.
- Signed-out, MFA, captcha, bot wall, unavailable, provider-failure, no-observation, budget, unsafe,
  and timeout paths are closed typed outcomes. Agentic failure never triggers an automatic legacy
  retry.

## Remaining Qualification Boundary

The adapter is ready for the offline qualification bolt and owner canary. This report does not
claim live Booking.com reliability or authorize invited-user routing.
