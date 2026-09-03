---
stage: test
bolt: 064-browser-use-price-executor
created: 2026-09-03T01:41:00Z
status: passed
---

# Test Report: Browser Use Price Executor

## Result

Bolt 064 passed its local quality gate and an isolated exact-candidate-image replay on the VPS.
Browser Use produced a current authenticated price observation that passed BookSaver's independent
query, evidence, refundability, currency, all-in, and qualified room-equivalence checks. No second
browser harness ran.

This completes construction of Unit 006. It does not complete Unit 003's 30-check, 14-day live
qualification or authorize invited-user promotion and legacy-selector retirement.

## Automated Verification

| Gate | Result |
|------|--------|
| Ruff over `src`, `tests`, and `scripts` | Passed |
| mypy strict project check | Passed: 129 source files |
| pytest | Passed: 1,925 tests; 55 existing deprecation warnings |
| CLI startup/help | Passed |
| specs.md artifact validator | Passed: 0 issues |
| specs.md status integrity | Passed: 0 inconsistencies |
| Git whitespace validation | Passed |
| Cursor Bugbot | Unavailable: official Cursor response reported its usage limit was reached |

Coverage includes default and explicit executor selection, shared manual/scheduled composition,
Browser Use action-registry confinement, trusted values, URL admission, atomic typed observation,
closed terminal mapping, model-view preflight, cost/deadline accounting, cleanup, policy-versioned
qualification, safe state cloning, and narrow room-rate suffix equivalence. Negative room variants
including different bed types and accessibility labels remain non-equivalent.

## VPS Exact-Image Replay

- Candidate source revision: `f5cea3597b57946d557a2643e6ea95bfc6797578`
- Image: `booksaver-agent:candidate-f5cea35`
- Image manifest: `sha256:b03466b2c99848bba0f3f4c62904cc0db64a3afcc7c4fd6833b177d91a68f84e`
- Execution path: isolated read-only clone of production state through the real coordinator and
  executor factories, with notifications disabled and no source mounts.
- Process result: exit 0; admission `accepted`; outcome `success`; completion `result`.
- Observation result: `valid_observation=true`; authenticated mobile-web source; USD price evidence.
- Safety result: 0 violations; no fallback.
- Duration: 81,436 ms.
- Model cost: USD 0.175276.

The candidate replay is below the USD 0.25 owner-canary average threshold and the USD 1/check hard
cap. A single run does not establish the average, p95, correctness comparison, or invited-user USD
0.10 promotion gates.

The repository's executable Bugbot gate was run and correctly rejected the PR because no review
could complete. The owner explicitly authorized merge when Bugbot was unavailable for this task;
the usage-limit response is treated as a documented review exception, not a clean Bugbot pass.

## Live Failure-to-Fix Evidence

The operator replay was kept in a loop until acceptance instead of stopping at model completion.
Content-free terminal evidence identified and verified fixes for:

- Stagehand remaining in the price operation's inventory prerequisite.
- A false transaction guard match on Booking.com's ISO-date `checkout` query parameter.
- URL attributes incorrectly passing through visible-label transaction scanning.
- Provider schema ambiguity and oversized query-bearing observed URLs.
- Search detours when a verified canonical property URL was already stored.
- Multi-call typed submission consuming the shared deadline.
- A recognized flexible-rate suffix preventing an otherwise exact room match.
- A redundant price-stage session refresh consuming residual time after current-run inventory
  verification.

No page text, screenshot, accessibility tree, prompt, cookie, credential, reservation fact, or model
reasoning was added to this report or persisted diagnostics.

## Residual Qualification Work

- Accumulate at least 30 eligible checks over at least 14 days.
- Manually compare at least 10 accepted observations with visible Booking.com offers.
- Re-evaluate reliability, average/p95 cost, p95 duration, and all critical-violation gates before
  any invited-user promotion.
- Keep Stagehand and deterministic execution as explicit future-job rollback choices; do not use a
  same-job fallback.
