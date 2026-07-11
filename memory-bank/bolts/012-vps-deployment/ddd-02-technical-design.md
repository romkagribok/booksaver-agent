---
unit: 005-vps-deployment
bolt: 012-vps-deployment
stage: design
status: complete
updated: 2026-07-11T20:05:00Z
---

# Technical Design — VPS Deployment (slice 1)

> Scope: US-034 in full, US-035 logged-out core only. No new runtime dependency — `SessionMode` is
> a plain `enum.Enum`; deployment artifacts add no Python dependency.

## Module Map — code

| Module | Role | New/Changed |
|--------|------|-------------|
| `domain/session.py` | + `SessionMode` enum (`LOGGED_OUT`, `AUTHENTICATED`), documented alongside `SessionStatus` | changed |
| `monitor/session_manager.py` | + `SessionManager.current_mode() -> SessionMode` — read-only, no `_repo.save()` call (unlike `ensure_active()`'s `EXPIRED` transition) | changed |
| `monitor/search_journey.py` | `SearchJourney.__init__` + `session_mode: SessionMode = SessionMode.AUTHENTICATED`; `_classify_failure` only returns `FailureCode.AUTH_REQUIRED` when `session_mode is AUTHENTICATED` | changed |
| `monitor/search_check_job.py` | `run_all_active()`: `session = ensure_active()`; `session is None` → `mode = LOGGED_OUT`, skip `restore_cookies`/`save_refreshed`, log once; else `mode = AUTHENTICATED`, existing cookie flow. `run_check(booking, session_mode=AUTHENTICATED)` and `_run_check_inner(..., session_mode)` thread the mode into `SearchJourney(...)`. Successful logged-out checks log a one-line "public rate" annotation (no schema field). `reauth_flagged`/`mark_reauth_required` logic only runs `if session is not None` | changed |

## Module Map — deployment/docs (new)

| Path | Role |
|------|------|
| `Dockerfile` | `python:3.12-slim` + `pip install .` + `playwright install --with-deps chromium`; non-root `booksaver` user; `/data` volume; `BOOKSAVER_CONFIG=/data/config.toml`; `ENTRYPOINT ["booksaver"]` / `CMD ["run"]` (foreground, per ADR-005) |
| `.dockerignore` | Excludes `.git`, `memory-bank`, `tests`, caches, and anything secret-shaped (`.env*`, `*.db`, `config.toml`) from the build context |
| `docker-compose.yml` | One service, `restart: unless-stopped`, `init: true` (zombie reaping for Chromium), required-secret env vars via `${VAR:?set in .env}`, named volume `booksaver-data:/data`, `mem_limit`/`memswap_limit` with a Chromium-sizing note, `healthcheck` (see TODO below) |
| `deploy/booksaver.service` | systemd unit: `Type=simple`, `EnvironmentFile=`, `User=`/`Group=`, `WorkingDirectory=`, `ExecStart=.../booksaver run`, `Restart=on-failure`, light sandboxing (`ProtectSystem=strict` + explicit `ReadWritePaths=`), header comment with the full install sequence |
| `memory-bank/operations/vps-deployment-runbook.md` | Provisioning → Docker install → secrets → config → first run → upgrade → backup → logs → systemd alternative → logged-out-checks smoke test + fallback ladder |
| `docs/DISCLAIMER.md` | Not-affiliated / ToS-risk-is-operator's / no-public-bot-mode statement |
| `README.md` | + "Deployment" section (links runbook/Dockerfile/compose/service) and "Disclaimer" section (links `docs/DISCLAIMER.md`) |

## Session-Mode Flow (US-035 logged-out core)

```
run_all_active():
  session = sessions.ensure_active()
  if session is None:
      mode = LOGGED_OUT
      # no restore_cookies, no save_refreshed — nothing to refresh
  else:
      mode = AUTHENTICATED
      browser.restore_cookies(session.cookies)   # unchanged from before this bolt

  for booking in bookings:
      result = run_check(booking, session_mode=mode)
      ...
      if session is not None and result is AUTH_REQUIRED:
          sessions.mark_reauth_required(session)   # unchanged; only reachable when session existed

  if session is not None:
      sessions.save_refreshed(session, browser.get_cookies())  # unchanged
```

```
SearchJourney._classify_failure(step):
  if captcha markers present: return BOT_WALL              # unaffected by session mode
  if session_mode is AUTHENTICATED and sign-in markers present:
      return AUTH_REQUIRED                                   # only reachable when a session existed
  return step-specific code (STEP_FAILED, PROPERTY_NOT_FOUND, ...)  # what logged-out mode falls through to
```

Backward compatibility: `SearchJourney(browser)` (no `session_mode` argument, used by every
pre-existing direct caller/test) defaults to `AUTHENTICATED`, so bolt 006/007 behavior for callers
that never think about session mode is byte-for-byte unchanged.

## Dockerfile base-image choice (documented, not a standalone ADR)

`python:3.12-slim` + explicit `playwright install --with-deps chromium`, rather than Microsoft's
`mcr.microsoft.com/playwright/python` image:

- Keeps the Python base version an explicit, current choice under our own control rather than
  whatever the Playwright image's release cadence bundles.
- The Playwright image includes multiple browser engines and test-runner tooling BookSaver never
  uses (only Chromium, via Playwright's **sync** API per ADR-007/008) — a larger image for no
  benefit.
- Matches the exact local dev setup already documented in `CLAUDE.md`/README
  (`playwright install chromium`), so there is one mental model for "how does BookSaver get a
  browser" across dev and prod.

Reversible: if browser/OS-dependency drift becomes a maintenance burden, switching the `FROM` line
to the Playwright image is a small, contained change (rebuild only), not an architectural one —
hence a code comment + runbook note rather than a numbered ADR.

## Healthcheck (deliberately deferred, flagged for the daemon/CLI owner)

`docker-compose.yml`'s `healthcheck` is `pgrep -f 'booksaver run' || exit 1` — process liveness
only. A real liveness probe (scheduler-loop or Telegram-poller progress, not just "the process
exists") needs a heartbeat file or small local endpoint written from inside `daemon/lifecycle.py`
or `cli/commands.py`'s `cmd_run`, both of which are owned by another in-flight worker this bolt
was instructed not to edit. Documented as a TODO in both the compose file and the runbook's "Open
items" section, addressed to that file's owner post-merge.

## Testing Strategy (stage 4)

- `tests/unit/monitor/test_session_and_failures.py`: `SessionManager.current_mode()` — no
  session → `LOGGED_OUT`; valid session → `AUTHENTICATED`; `REQUIRES_REAUTH` → `LOGGED_OUT`;
  expired → `LOGGED_OUT`; confirms it does **not** mutate the stored session (unlike
  `ensure_active()`).
- `tests/unit/monitor/test_search_journey.py`: a "sign in" page in `LOGGED_OUT` mode never
  classifies as `AUTH_REQUIRED`; a captcha in `LOGGED_OUT` mode still classifies as `BOT_WALL`
  (session mode never overrides bot-wall detection).
- `tests/unit/monitor/test_search_check_job.py`: `run_all_active()` with no session runs every
  booking to completion (via the existing DOM-happy-path fixture) instead of failing them all with
  `AUTH_REQUIRED`; confirms no cookies were restored in that path.
- Dockerfile/compose/systemd: reviewed line-by-line; `docker compose config` was run successfully
  to validate YAML/interpolation syntax. **Not build/run tested** — no Docker daemon available in
  this execution environment (`docker info` fails to reach the daemon). Flagged in
  `ddd-03-test-report.md` and the bolt's success criteria for the orchestrator to build/run once
  merged, ideally directly on a target VPS as the runbook's §5/§10 describe.

## Slice 2 — Cookie Import (US-035 remainder)

### Module Map — code (new/changed)

| Module | Role | New/Changed |
|--------|------|-------------|
| `infrastructure/persistence/cookie_import.py` | `import_cookies(raw_text, now) -> tuple[SessionState, ImportSummary]` — parse, validate, normalize, build a storable `SessionState`. `CookieImportError` for anything unusable. | new |
| `cli/commands.py` | `cmd_auth_import` + `auth` gains an `import` subparser (`booksaver auth import <file>`); bare `booksaver auth` unchanged (headed login, `p_auth`'s own `set_defaults`) | changed (scoped strictly to the `auth` parser/handler, per the bolt-011 coordination boundary) |
| `monitor/session_manager.py` | Warning/log text in `ensure_active()` and `mark_reauth_required()` now mentions `booksaver auth import <file>` alongside headed `booksaver auth` | changed |
| `monitor/search_check_job.py` | `_run_check_inner`'s `AUTH_REQUIRED` failure detail appends a `booksaver auth import` hint; `_to_success` now threads `session_mode` into `CheckResult.success()` | changed |
| `domain/check_result.py` | `CheckResult.session_mode: SessionMode \| None = None` — deliberately unpersisted (see its docstring); `CheckResult.success()` gains the same optional parameter | changed |
| `application/savings_pipeline.py` | `render_alert(opportunity, booking, session_mode=None)` appends "(public rate — member deals may be cheaper)" to the live-price line when `session_mode is LOGGED_OUT`; `NotificationDispatcher.dispatch()` and `SavingsPipeline.process()` thread `result.session_mode` through | changed |
| `memory-bank/operations/vps-deployment-runbook.md` | New §11 "Cookie import for member/Genius rates"; §10 updated to reference `/status`/`/register`/rebook now that Units 001–004 shipped | changed |
| `README.md` | New "Telegram bot" section; Deployment section mentions cookie import | changed |

### Cookie shape normalization (`cookie_import.py`)

Two input shapes accepted, both normalized to Playwright's `context.add_cookies()` shape:

1. **Playwright native** (what `booksaver auth`'s `interactive_login()` itself produces): `expires`
   as a float epoch-seconds (or `-1` for a session cookie), `sameSite` already one of
   `"Strict"`/`"Lax"`/`"None"`.
2. **Browser-extension export** (Cookie-Editor, EditThisCookie, and similar): `expirationDate`
   instead of `expires`, `sameSite` as a Chrome-flavored string (`"no_restriction"`, `"lax"`,
   `"strict"`, `"unspecified"`).

Normalization rules:

- `sameSite`: exact `"Strict"`/`"Lax"`/`"None"` passed through; `"no_restriction"` → `"None"`,
  `"unspecified"`/missing/unrecognized → `"Lax"` (Playwright's own default for an omitted
  `sameSite`).
- `expires`: prefers `expirationDate` then `expires`; anything not a positive number → `-1.0`
  (Playwright's "no explicit expiry" sentinel, used for session cookies).
- `domain`/`path`/`httpOnly`/`secure`: passed through with safe defaults (`path="/"`,
  `httpOnly=False`, `secure=True` — booking.com is HTTPS-only).

### Validation order (fail before any write)

```
parse JSON (CookieImportError: "not valid JSON")
  -> normalize each entry, drop ones missing name/value/domain
  -> CookieImportError("no usable cookie objects found") if none normalize
  -> filter to booking.com-domain cookies (domain.lstrip(".").endswith("booking.com"))
  -> CookieImportError("no cookies for a booking.com domain") if none
  -> CookieImportError("already expired") if every booking.com cookie's expiry has passed
  -> build SessionState (only now is anything constructed for storage)
```

`import_cookies()` never partially stores a rejected file — the caller (`cmd_auth_import`) only
calls `LocalSessionRepository.save()` after `import_cookies()` returns successfully.

### Session-level expiry choice

`SessionState.expires_at` is set to the **earliest** explicit expiry among the imported
booking.com cookies (cookies with no explicit expiry don't contribute). This is a deliberate
simplification: it means `SessionManager.ensure_active()`/`current_mode()` — unchanged from
slice 1 — will report the whole session as `EXPIRED`/`LOGGED_OUT` as soon as any one imported
cookie goes stale, even if others remain valid longer. Conservative in the safe direction (never
serves a stale-cookie-backed price as if it were still authenticated) at the cost of possibly
re-importing somewhat earlier than strictly necessary. No new code was needed in
`SessionManager` for expiry-driven fallback — slice 1's existing `is_expired()`/`ensure_active()`
logic (already tested) does the work; only the log-message wording changed.

### `CheckResult.session_mode`: in-memory-only, no schema change

The bolt's coordination boundary keeps `check_history`/`check_traces` schema ownership with other
workers. Rather than add a persisted column, `CheckResult` gained an **unpersisted** optional
`session_mode` field: `BookingComSearchMonitor.run_all_active()` produces a `list[CheckResult]`
that `SavingsPipeline.process()` consumes immediately afterwards, in the same scheduler tick
(`cli/commands.py`'s `_make_check_job`). The field only needs to survive that one in-process hop —
`SqliteCheckHistoryRepository.add()` picks named attributes off `CheckResult` explicitly and
ignores unknown ones, so the extra field is silently harmless to persistence, requiring zero
schema/migration work. Every pre-slice-2 call site (`CheckResult.success(...)` without
`session_mode`, `render_alert(...)` without `session_mode`) defaults to `None`, which renders
identically to the pre-slice-2 alert body — verified by
`test_render_alert_omits_public_rate_label_when_session_mode_unknown`.

### `auth import` CLI shape

Chosen over `--import-file <path>`: mirrors the existing `bookings`/`checks` subcommand pattern
(`bk_sub = p_bk.add_subparsers(...)`) already used elsewhere in `create_parser()`, reads more
naturally (`booksaver auth import cookies.json` vs. a flag on a command whose bare form does
something entirely different), and keeps `booksaver auth --help` showing "import" as a discoverable
subcommand rather than a buried flag. `p_auth.set_defaults(func=cmd_auth)` is set before
`p_auth.add_subparsers(...)`, so bare `booksaver auth` (no subcommand) keeps invoking headed login
unchanged — verified by `test_bare_auth_still_routes_to_headed_login`.

### Testing Strategy (slice 2)

- `tests/unit/test_cookie_import.py` (22 tests): both accepted shapes, `{"cookies": [...]}`
  unwrapping, session-cookie-without-expiry handling, sameSite/expires normalization
  (parametrized), all four rejection cases (malformed JSON, non-array, no booking.com cookie, all
  expired), partial-expiry acceptance, empty-array/missing-fields rejection, and a check that
  error messages never echo a cookie value.
- `tests/unit/test_cli_auth_import.py` (7 tests): happy path (stdout content, 0600 permission,
  cookie value absent from the stored file), mode flip to `AUTHENTICATED` via
  `SessionManager.current_mode()`, all four rejection paths surfacing as exit code 2 with actionable
  stderr, missing-file handling, and that bare `auth` still resolves to `cmd_auth`.
- `tests/unit/monitor/test_session_and_failures.py` (+2): `mark_reauth_required` and the
  expired-session path in `ensure_active` both log text containing `booksaver auth import`
  (`caplog`-based).
- `tests/unit/monitor/test_search_check_job.py` (+1): an `AUTH_REQUIRED` failure (session existed,
  journey still landed signed-out) has `booksaver auth import` in its `failure_reason.detail`.
- `tests/unit/savings/test_pipeline.py` (+4): `render_alert` includes/omits the public-rate label
  correctly for `LOGGED_OUT`/`AUTHENTICATED`/unset `session_mode`, plus one end-to-end
  `SavingsPipeline.process()` test confirming the label reaches the dispatched alert body.
