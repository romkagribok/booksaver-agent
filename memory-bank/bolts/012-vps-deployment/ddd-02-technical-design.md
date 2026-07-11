---
unit: 005-vps-deployment
bolt: 012-vps-deployment
stage: design
status: complete
updated: 2026-07-11T17:50:00Z
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
