# Construction Log: VPS Deployment

**Intent:** `003-telegram-interface`
**Unit:** `005-vps-deployment`
**Status:** In progress (bolt 012, slice 1 of 2 complete)

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
