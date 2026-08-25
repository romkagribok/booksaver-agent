---
stage: test
bolt: 054-local-agentic-price-executor
created: 2026-08-25T01:18:33Z
status: complete
---

# Test Report: Container-Compatible Stagehand Launch

## Summary

- **Focused tests**: 34 passed.
- **Repository tests**: 1,695 passed with 55 existing schedule-deprecation warnings.
- **Static quality**: Ruff passed; strict mypy passed across 124 source files.
- **AI-DLC integrity**: artifact validation and status integrity passed with zero issues.
- **Runtime/package smoke**: CLI/config validation passed; Stagehand is exactly 4.0.1.
- **Exact-image smoke**: `booksaver-agent:staging-d6ef5b2`
  (`sha256:a8b1ae357ad69da48bd7352c1589827af9916ebd008845bf08fba310d7edf790`)
  launched, attached through loopback CDP, confined telemetry to loopback, and tore down with `CI`
  absent.

## Acceptance Criteria Validation

- ✅ **Explicit compatibility**: the adapter passes `chromium_sandbox=False` directly to Stagehand.
- ✅ **Unprivileged runtime**: the image remains `USER booksaver`; no privileged mode, root browser,
  host browser service, or added capability exists.
- ✅ **Regression coverage**: the unit seam asserts the exact Stagehand launch arguments and close.
- ✅ **Production-image lifecycle**: the immutable Linux image completed launch, attachment, and
  teardown without `CI`; no smoke container remained afterward.
- ✅ **Preserved boundaries**: all existing browser executor, session, guard, routing, qualification,
  configuration, and persistence tests passed unchanged.

## Production Safety Evidence

The smoke was content-free and did not use an Anthropic API key, authenticated Booking.com session,
or live owner check. The running production BookSaver container remained on the prior image,
`running/healthy`, with zero restarts throughout the test.

## Issues Found

None after the explicit launch correction.

## Remaining Qualification Work

This smoke qualifies packaging only. Bolt 052 still requires 30 authentic owner checks over at least
14 days, 10 manual price comparisons, all quantitative gates, and explicit owner promotion before
invited-user agentic routing.
