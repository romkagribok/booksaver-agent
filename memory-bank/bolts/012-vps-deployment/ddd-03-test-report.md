---
unit: 005-vps-deployment
bolt: 012-vps-deployment
stage: test
status: complete
updated: 2026-07-11T20:10:00Z
---

# Test Report — VPS Deployment (slice 1: US-034 + logged-out core; slice 2: cookie import)

## Summary (current, after slice 2)

| Metric | Value |
|--------|-------|
| Total tests | **609 passed, 0 failed** |
| New in slice 2 | 36 |
| New in slice 1 (net) | 7 |
| Pre-bolt baseline | 360 — all still green |
| Lint (`ruff check src/ tests/`) | clean |
| Types (`mypy src/`) | clean (71 source files) |
| Test command | `PYTHONPATH=src python3 -m pytest` |

## Slice 2 New Test Coverage (US-035 remainder — cookie import)

- `tests/unit/test_cookie_import.py` (22): `test_import_playwright_native_shape`,
  `test_import_browser_extension_export_shape` (verifies only the booking.com cookie survives
  filtering, `sameSite` normalized from `"no_restriction"`), `test_wrapped_in_cookies_key_is_unwrapped`,
  `test_session_cookie_without_expiry_is_accepted_and_not_flagged_expired`, 9 parametrized
  `test_same_site_normalization` cases, `test_expires_normalized_to_float_seconds`,
  `test_rejects_malformed_json`, `test_rejects_non_array_non_wrapped_json`,
  `test_rejects_no_booking_domain_cookies`, `test_rejects_all_expired_cookies`,
  `test_partial_expiry_is_accepted_when_at_least_one_cookie_is_valid` (confirms session-level
  `expires_at` is the *earliest* cookie's expiry), `test_rejects_empty_array`,
  `test_rejects_cookies_missing_required_fields`, `test_error_messages_never_include_cookie_values`.
- `tests/unit/test_cli_auth_import.py` (7): `test_auth_import_happy_path_stores_session` (stdout
  content, 0600 file permission, cookie value absent from both stdout and the stored file),
  `test_auth_import_flips_mode_to_authenticated` (via `SessionManager.current_mode()`),
  `test_auth_import_rejects_garbage_file`/`_no_booking_domain`/`_all_expired` (exit code 2,
  actionable stderr, no session file written on rejection), `test_auth_import_missing_file`,
  `test_bare_auth_still_routes_to_headed_login` (the `import` subparser doesn't shadow the
  default `cmd_auth` handler for bare `booksaver auth`).
- `tests/unit/monitor/test_session_and_failures.py` (+2):
  `test_mark_reauth_required_mentions_vps_compatible_cookie_import`,
  `test_ensure_active_expired_session_log_mentions_cookie_import` — both `caplog`-based, confirm
  `"booksaver auth import"` appears in the warning text.
- `tests/unit/monitor/test_search_check_job.py` (+1):
  `test_auth_required_detail_points_at_cookie_import` — a session existed (`AUTHENTICATED`) but
  the journey still landed on a signed-out page; `failure_reason.detail` must contain
  `"booksaver auth import"`.
- `tests/unit/savings/test_pipeline.py` (+4): `test_render_alert_labels_logged_out_price_as_public_rate`,
  `test_render_alert_omits_public_rate_label_when_authenticated`,
  `test_render_alert_omits_public_rate_label_when_session_mode_unknown` (regression guard: every
  pre-slice-2 caller keeps an identical alert body), `test_pipeline_dispatches_public_rate_label_through_end_to_end`.

## Slice 2 Regression Statement

`CheckResult.session_mode` is a new field with `default=None` and is not read by
`SqliteCheckHistoryRepository.add()` (which picks named attributes explicitly) — no persistence
behavior changed. `render_alert()`'s new `session_mode` parameter defaults to `None`, which renders
byte-for-byte identical to the pre-slice-2 alert body (asserted directly). `CheckResult.success()`'s
new `session_mode` parameter is likewise optional and defaults to `None`, so every pre-slice-2 call
site is unaffected. `SessionManager`'s log-message wording changed but not its control flow
(`ensure_active`/`mark_reauth_required`'s existing 5 tests plus the 2 new `caplog` tests all pass).
`_run_check_inner`'s `AUTH_REQUIRED` detail text is now longer but still starts with the same
`step=...: ...` prefix every pre-slice-2 test asserted on
(`test_failed_step_lands_in_failure_detail` uses `PROPERTY_NOT_FOUND`, untouched by the
`AUTH_REQUIRED`-only branch). All 360 pre-bolt tests and all 7 slice-1 tests remain green.

## Slice 2 Not Covered (accepted, and why)

- **A Telegram file-upload path for cookie import** (bot-side, with immediate message deletion) —
  not implemented; the CLI path (`booksaver auth import`) fully satisfies US-035's acceptance
  criteria on its own, and this bolt's coordination boundary keeps
  `infrastructure/telegram/` owned by the parallel bolt-011 worker. Documented as a possible
  future enhancement, not a gap, in the runbook and construction log.
- **Live cookie-export-and-import against a real Booking.com account** — inherently a manual,
  on-target-hardware/browser activity; the runbook's §11 documents the exact extension flows
  (Cookie-Editor, EditThisCookie) for an operator to follow. Unit tests instead construct synthetic
  cookie exports in both accepted shapes.

---

# Slice 1 Report (as originally filed)

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
- ~~**Cookie import (US-035 remainder)**~~ — RESOLVED in slice 2 (see the top of this report):
  `booksaver auth import <file>`, `cookie_import.py`, expiry → re-import prompt, and public-rate
  alert labeling are all implemented and tested.
- **`/status` surface** — Unit 001 (`telegram-bot-gateway`) shipped `/status`
  (`infrastructure/telegram/commands_readonly.py`), but it doesn't render session mode explicitly
  yet; `SessionManager.current_mode()` remains available for that module's owner to call. Left
  untouched here per this bolt's coordination boundary (no `infrastructure/telegram/` changes).
