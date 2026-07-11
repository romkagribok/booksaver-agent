# Construction Log: VPS Deployment

**Intent:** `003-telegram-interface`
**Unit:** `005-vps-deployment`
**Status:** Complete (bolt 012, both slices)

## Bolt 012-vps-deployment (slice 2 — cookie import + docs finalization)

- **Started:** 2026-07-11T19:40:00Z
- **Completed:** 2026-07-11T20:10:00Z
- **Stage reached:** test (complete)
- **Stories:** US-035 (complete — cookie-import remainder)

### What shipped

- `src/booksaver/infrastructure/persistence/cookie_import.py`: `import_cookies()` parses,
  validates, and normalizes a cookie export (both Playwright's native `context.cookies()` shape
  and the common browser-extension export shape — `expirationDate`/`sameSite` string variants) into
  a storable `SessionState`, via the existing `LocalSessionRepository` (same file, same 0600 care).
  Rejects malformed JSON, files with no booking.com-domain cookie, and files where every
  booking.com cookie is already expired — all before anything is written to disk. Session-level
  `expires_at` is set to the earliest imported cookie's expiry (conservative: the whole session is
  treated as needing re-import as soon as any one cookie goes stale).
- `booksaver auth import <file>` (`src/booksaver/cli/commands.py`, `cmd_auth_import` + an `auth`
  subparser): the VPS-compatible alternative to headed `booksaver auth`. Prints count/domains/
  earliest-expiry on success — never cookie values. Bare `booksaver auth` is unchanged (still
  headed login).
- `SessionManager` (`monitor/session_manager.py`) warning/log text and the search-journey
  `AUTH_REQUIRED` failure detail (`monitor/search_check_job.py`) now mention
  `booksaver auth import <file>` explicitly as the VPS-compatible fix, so an expired/dropped
  session never degrades silently to logged-out prices without a clear next step.
- `CheckResult.session_mode` (`domain/check_result.py`, new optional field, deliberately not
  persisted — see its docstring) threads which session mode produced a live price from
  `BookingComSearchMonitor` through to `SavingsPipeline` within the same scheduler tick;
  `render_alert()` (`application/savings_pipeline.py`) appends "(public rate — member deals may be
  cheaper)" to the live-price line when that mode was `LOGGED_OUT`.
- Runbook §11 "Cookie import for member/Genius rates" (export how-to for Cookie-Editor/
  EditThisCookie, the CLI import command, expiry behavior, and the "treat like a password" security
  caution) + §10 updated to reference `/status`/`/register`/the Telegram rebook flow, now that
  Units 001–004 have shipped. README: new "Telegram bot" section + a cookie-import mention in
  "Deployment".

### What's deferred (acceptable, not blocking)

- A Telegram file-upload path for cookie import (bot-side, with immediate message deletion) —
  the CLI path (`booksaver auth import`) fully satisfies US-035's acceptance criteria on its own;
  a bot-upload path is a possible future UX enhancement, not a gap.
- Session-level expiry uses the *earliest* imported cookie's expiry rather than tracking each
  cookie's own lifetime individually — a deliberate simplification (documented in
  `cookie_import.py` and the runbook) that may prompt a re-import somewhat earlier than strictly
  necessary; never later.

### Test status at close of this slice

609 tests passing (573 from Waves 1–2 + 36 new/changed: cookie-import parsing/validation/
normalization, CLI happy-path/rejection/mode-flip, session-manager/failure-detail wording, and
public-rate alert labeling), `ruff check src/ tests/` clean, `mypy src/` clean.

## Bolt 012-vps-deployment (slice 1)

- **Started:** 2026-07-11T17:30:00Z
- **Stage reached:** test (complete for this slice)
- **Stories:** US-034 (complete), US-035 (logged-out core complete; cookie import pending)

### What shipped

- `SessionMode` domain concept (`src/booksaver/domain/session.py`): `LOGGED_OUT` vs
  `AUTHENTICATED`, exposed read-only via `SessionManager.current_mode()`
  (`src/booksaver/monitor/session_manager.py`) for a future `/status` command.
- `SearchJourney` (`src/booksaver/monitor/search_journey.py`) now takes a `session_mode` and
  gates `FailureCode.AUTH_REQUIRED` classification on it — impossible to produce while logged
  out.
- `BookingComSearchMonitor.run_all_active()` (`src/booksaver/monitor/search_check_job.py`) no
  longer fails every booking when no session file exists; it runs the full search journey
  logged out and records real public prices, logging (not persisting — schema owned elsewhere)
  that a successful check used a public rate.
- `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `deploy/booksaver.service` at repo root.
- `memory-bank/operations/vps-deployment-runbook.md` — provisioning through the VPS-IP
  logged-out-checks smoke test and its fallback ladder (lower frequency → home server →
  residential proxy).
- `docs/DISCLAIMER.md` + linked README sections (Deployment, Disclaimer).

### What's deferred to the next slice

- Cookie-import CLI command (and optional Telegram file-upload path) for member/Genius rates —
  the rest of US-035.
- `/status` wiring to `SessionManager.current_mode()` — belongs to Unit 001
  `telegram-bot-gateway`.
- A real liveness healthcheck (heartbeat file or endpoint) to replace the process-liveness
  `pgrep` check in `docker-compose.yml` — needs changes in `daemon/lifecycle.py` /
  `cli/commands.py`, owned by a parallel worker; documented as a TODO in both the compose file
  and the runbook.
- `docker build .` / `docker compose up -d` verification against a live Docker daemon — none was
  reachable in this development environment; Dockerfile/compose were reviewed line-by-line and
  `docker compose config` was used to validate syntax instead.

### Coordination notes

Ran alongside two parallel workers (Telegram gateway/daemon/CLI; SQLite schema/repositories).
This slice's code changes were scoped to `monitor/session_manager.py`,
`monitor/search_journey.py`, `monitor/search_check_job.py`, and `domain/session.py` only — no
`daemon/`, `cli/commands.py`, `schema.sql`, or repository files were touched, per the
coordination boundary for this bolt.

### Test status at close of this slice

367 tests passing (360 pre-existing + 7 net new/changed), `ruff check src/` clean, `mypy src/`
clean. See `memory-bank/bolts/012-vps-deployment/ddd-03-test-report.md` for the full breakdown.
