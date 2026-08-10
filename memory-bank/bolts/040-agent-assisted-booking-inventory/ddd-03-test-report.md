---
unit: 002-agent-assisted-booking-inventory
bolt: 040-agent-assisted-booking-inventory
stage: test
status: complete
updated: 2026-08-10T16:46:13Z
---

# Test Report - Current-Evidence Inventory Recovery

## Outcome

The production `inventory_upcoming_url` failure shape is reproduced with a fresh `about:blank`
baseline, an allowlisted authenticated current page, and a readiness-style exception. Recovery now
classifies the current page, retains the original page only as the progress baseline, and reaches
the existing named verifier. Unavailable, authentication, captcha, and unapproved current evidence
all stop before recovery-factory construction, LLM disclosure, or browser action.

## Verification Summary

| Gate | Result |
|---|---:|
| Production-shaped inventory browser regressions | 43 passed |
| Inventory/coordinator/Telegram/persistence focused set | 133 passed |
| Full repository suite | 1230 passed |
| Ruff across `src` and `tests` | Passed |
| Strict mypy across 103 source files | Passed |
| CLI/config/help smoke with `PYTHONPATH=src` | Passed |
| AI-DLC artifact validator | Passed |
| AI-DLC status integrity | Passed |
| Diff whitespace validation | Passed |
| Independent security review | No findings |
| Independent correctness/test review | One test-strength finding, closed |

The full suite emitted 49 expected legacy `schedule.check_interval` deprecation warnings; no test
failed. The first CLI smoke attempt used an uninstalled module path and failed with
`ModuleNotFoundError`; rerunning through the repository-native `PYTHONPATH=src` path passed.

## Acceptance Criteria Validation

- ✅ Fresh current evidence supersedes stale `about:blank` for auth, captcha, and allowlist safety
  classification.
- ✅ The original pre-navigation observation remains the verifier progress baseline; the regression
  test executes the verifier and would fail if the current observation replaced that baseline.
- ✅ Missing current evidence records unavailable and never constructs the recovery agent.
- ✅ Current captcha, auth-required, and unapproved destinations remain fail closed with specific
  existing outcomes and zero recovery actions.
- ✅ Warning diagnostics contain only step, exception class, and approved/unapproved/unavailable
  category. Tests prove private exception text, host, path, and query values are excluded.
- ✅ No allowlist, selector, action guard, completeness, reconciliation, schema, provider, or public
  interface changed.

## Regression Coverage

- Fresh `about:blank` → current allowlisted `mytrips` → readiness timeout → guarded handoff.
- Available current evidence plus original baseline → named verifier succeeds.
- Previously available baseline plus unavailable current observation → unavailable, no stale fallback.
- Current account-settings/private-query destination → blocked, no agent, content-free logs.
- Current captcha and sign-in evidence → specific bot-wall/auth-required outcomes, no agent.
- Existing inventory parsing, guarded actions, interpretation, completeness, coordinator,
  reconciliation, and Telegram freshness behavior through focused and full suites.

## Review Findings

The security review found no P0/P1/P2 issues. The correctness review found that the first version of
the production-shaped test did not execute the supplied verifier and therefore could not prove the
baseline invariant. The test was strengthened to call the verifier and assert success; focused
tests and lint were rerun successfully.

## Deferred Live Acceptance

No service, VPS, Telegram, Booking.com, database, or provider mutation was made during construction.
After the pre-merge review and a separate deployment decision, acceptance remains a human
`/bookings` refresh followed by `/checknow` for an eligible reservation through the sole production
coordinator.
