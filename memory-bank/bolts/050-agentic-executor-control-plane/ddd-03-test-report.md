---
stage: test
bolt: 050-agentic-executor-control-plane
created: 2026-08-17T03:23:22Z
status: complete
---

# Test Report: Agentic Executor Control Plane

## Summary

- **Focused contract/config tests**: 64 passed.
- **Repository suite**: 1,603 passed, 55 existing deprecation warnings.
- **Ruff**: all source and tests passed.
- **Strict mypy**: 120 source files passed.
- **Diff integrity**: no whitespace errors.

## Acceptance Criteria Validation

- **US-143**: Provider-neutral request/result contracts contain only typed query/evidence/metric
  fields; fake executor covers deterministic responses. Complete.
- **US-144**: Property, date, occupancy, authentication, currency, all-in, completeness, and explicit
  refundability failures reject independently. Complete.
- **US-145**: Opaque owner/job-bound leases are single-use, content-safe in repr/results, close on
  exceptions, and retain refresh only after code verification. Complete.
- **US-146**: Legacy defaults, owner-only canary, invited-user qualification/consent, regression
  rollback, 15/6 action limits, and exact micro-USD job limits are tested. Complete.

## Security and Privacy Tests

- Contract field introspection rejects cookie/session/page/screenshot/tree/prompt/reasoning surfaces.
- Session material is pushed into a code-owned target and never returned by lease restoration.
- Invalid lease binding, reuse, expiry, and unverified refresh fail closed.
- Executor results that exceed admitted limits are rejected before offer policy.

## Issues Found

No unresolved issues. One Ruff line-length issue was corrected before the full gate.

## Recommendations

- Bolt 051 must use the broker's push interface so Stagehand/Anthropic never receive raw session
  values through provider-facing objects.
- Keep `legacy` runtime composition unchanged until the local adapter and qualification bolts pass.
