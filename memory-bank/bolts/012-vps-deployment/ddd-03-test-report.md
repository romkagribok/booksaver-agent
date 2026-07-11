---
unit: 005-vps-deployment
bolt: 012-vps-deployment
stage: test
status: complete
updated: 2026-07-11T18:10:00Z
---

# Test Report — VPS Deployment (slice 1: US-034 + logged-out core of US-035)

## Summary

| Metric | Value |
|--------|-------|
| Total tests | **367 passed, 0 failed** |
| New in this bolt | 7 (net: 1 existing test rewritten to match the new logged-out behavior, 6 added) |
| Pre-existing (regression surface) | 360 — all green |
| Lint (`ruff check src/`) | clean |
| Types (`mypy src/`) | clean (51 source files) |
| Test command | `PYTHONPATH=src python3 -m pytest` |

## New/Changed Test Coverage by Story

### US-035 (logged-out core) — 7 tests

- `tests/unit/monitor/test_session_and_failures.py` (+5):
  `test_current_mode_logged_out_when_no_session`,
  `test_current_mode_authenticated_when_valid_session`,
  `test_current_mode_logged_out_for_reauth_required`,
  `test_current_mode_logged_out_for_expired_session`,
  `test_current_mode_does_not_mutate_stored_session` — the last confirms
  `current_mode()` is a pure read (`repo.session is session` after the call), unlike
  `ensure_active()`'s `EXPIRED`-transition side effect covered by the pre-existing
  `test_ensure_active_expires_session_past_expiry`.
- `tests/unit/monitor/test_search_journey.py` (+2):
  `test_signed_out_page_never_classified_as_auth_required_when_logged_out` — a "Log in
  to your account" banner with `session_mode=LOGGED_OUT` falls through to the
  step-specific failure code, never `AUTH_REQUIRED`;
  `test_captcha_still_wins_over_step_code_when_logged_out` — confirms session mode
  never suppresses `BOT_WALL` classification (captcha detection is independent of
  session state).
- `tests/unit/monitor/test_search_check_job.py` (rewritten, 0 net new): replaced
  `test_no_session_records_auth_failure_per_booking` (which asserted the *old*
  behavior — every booking failing `AUTH_REQUIRED` when no session exists) with
  `test_no_session_runs_logged_out_instead_of_failing`, which asserts both bookings
  now **succeed** via the happy-path DOM fixture and that `browser.restored_cookies`
  stays empty (no cookie-restore attempt without a session to restore).

### US-034 — 0 automated tests (infrastructure/docs artifact)

Dockerfile, `docker-compose.yml`, `deploy/booksaver.service`, `.dockerignore`, and the runbook are
infrastructure-as-config, not Python — there is no unit-test surface for them in this repo's
existing test suite shape (consistent with how bolt 002's `daemon`/scheduler infra was verified
manually rather than via pytest). Verification performed instead:

- `docker compose config` (with placeholder secret env vars) parses `docker-compose.yml`
  successfully — confirms YAML syntax, variable interpolation (`${VAR:?...}` required-secret
  guards), volume/healthcheck/mem-limit keys are well-formed.
- Dockerfile reviewed line-by-line for: non-root user before `ENTRYPOINT`, `playwright install
  --with-deps chromium` run before the `USER` switch (needs root for `apt`), `procps` present in
  the base `apt-get install` (required for the compose healthcheck's `pgrep`), no secrets
  `COPY`'d or `ARG`'d into any layer, `.dockerignore` excludes `.env*`/`*.db`/`config.toml` from
  the build context.
- **`docker build .` was not run** — no Docker daemon is reachable in this execution environment
  (`docker info` errors with "Cannot connect to the Docker daemon"). This is flagged as an
  explicit open item: the orchestrator (or whoever merges this branch) should run `docker build .`
  and a real `docker compose up -d` against the runbook's §5 before treating US-034 as fully
  verified end-to-end, and ideally follow through to §10's VPS-IP smoke test on a real VPS.

## Regression Statement

All 360 pre-existing tests pass unchanged. The behavior change in `run_all_active()` (no session →
proceed logged-out instead of failing every booking) is the only behavioral change to a
pre-existing code path in this bolt, and it is exactly the change US-035 calls for; the one test
that encoded the old behavior was updated deliberately, not broken incidentally.
`SearchJourney(browser)` without a `session_mode` argument (every pre-existing call site) keeps
defaulting to `AUTHENTICATED`, so bolt 006/007 journey/escalation behavior is unaffected.

## Not Covered (accepted, and why)

- **Live VPS-IP validation** (runbook §10) — inherently an operations-phase, on-target-hardware
  activity; cannot be exercised in this development environment. The runbook documents the exact
  steps and how to interpret each outcome.
- **Docker build/run** — no daemon available here (see above); reviewed by hand instead.
- **Cookie import (US-035 remainder)** — out of scope for this slice by design; no code exists
  yet to test. The next slice should add: cookie-file parsing/validation, storage alongside
  `session_booking_com.json` with the same permission care, expiry → re-import prompt (not silent
  degradation), and a CLI import command (`ddd-01`/`ddd-02` for that slice will define the exact
  shape).
- **`/status` surface** — depends on Unit 001 (`telegram-bot-gateway`), owned by a parallel
  worker; `SessionManager.current_mode()` is the accessor it should call once that lands.
