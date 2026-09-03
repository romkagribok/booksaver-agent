---
stage: test
bolt: 065-shared-browser-use-access
created: 2026-09-03T23:40:05Z
---

# Test Report: Shared Browser Use Access

## Outcome

Bolt 065 passes its focused and repository-wide quality gates. The implementation admits active,
currently disclosed invitees through the explicit `consented_users` Browser Use price route while
preserving disclosure, regression, authorization, cost, and safety boundaries. The owner-only
Telegram projection reports the current funding policy and coarse personal legacy-key presence
without returning or decrypting key material.

## Acceptance Coverage

| Story | Evidence | Result |
|-------|----------|--------|
| US-170 | Route unit tests cover owner, current/missing/stale invitee consent, regression, legacy, canary, qualified mode, and config parsing. Coordinator coverage proves an unqualified currently disclosed invitee constructs the existing agentic price path. Existing coordinator tests prove manual and scheduled triggers share that path. | Pass |
| US-171 | Repository-backed command tests cover configured/not-configured key presence, fixed owner funding, command/callback parity, unavailable runtime counters, non-owner refusal, and raw-key/exact-record sentinels. | Pass |

## Verification Results

- Focused behavior suite: `141 passed`.
- Full test suite: `1931 passed`, with 55 pre-existing schedule deprecation warnings.
- Ruff: all checks passed.
- mypy: no issues in 129 source files.
- CLI smoke: `python3 -m booksaver.cli --help` passed.
- specs.md artifact validator: 0 issues.
- specs.md status-integrity check: 0 inconsistencies across 65 bolts and 23 intents.
- Whitespace/error-marker check: passed.

## Security Review

- Browser Use factories still receive only the deployment environment key.
- Invitees still require exact current disclosure consent before agentic page processing.
- Recorded regression still takes precedence over `consented_users`.
- The admin query evaluates only `encrypted_key IS NULL`; it never selects or decrypts the blob.
- Telegram tests seed recognizable secrets and exact booking/check facts and prove they are absent.
- No schema migration, new secret, transaction authority, or same-job fallback was introduced.

## Residual Operational Requirement

Merge does not mutate a deployment's bind-mounted configuration. The owner must explicitly set
`agentic_browser.routing = "consented_users"` in production and redeploy in a later operations step.
Invitees with missing or stale disclosure consent must complete `/connect` and accept the current
version before Browser Use admission.
