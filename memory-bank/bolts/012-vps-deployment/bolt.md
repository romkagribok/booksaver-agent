---
id: 012-vps-deployment
unit: 005-vps-deployment
intent: 003-telegram-interface
type: ddd-construction-bolt
status: complete
stories:
  - 001-deploy-on-vps
  - 002-logged-out-checks-and-cookie-import
created: 2026-07-11T17:30:00Z
started: 2026-07-11T17:30:00Z
completed: 2026-07-11T20:10:00Z
current_stage: test
stages_completed:
  - name: model
    completed: 2026-07-11T17:45:00Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-11T17:50:00Z
    artifact: ddd-02-technical-design.md
  - name: implement
    completed: 2026-07-11T18:05:00Z
    artifact: >
      domain/session.py (SessionMode) + monitor/session_manager.py
      (current_mode) + monitor/search_journey.py (session_mode gate on
      AUTH_REQUIRED) + monitor/search_check_job.py (logged-out fallback in
      run_all_active) + Dockerfile + docker-compose.yml + .dockerignore +
      deploy/booksaver.service + memory-bank/operations/vps-deployment-runbook.md
      + docs/DISCLAIMER.md + README.md deployment/disclaimer sections
  - name: test
    completed: 2026-07-11T18:10:00Z
    artifact: ddd-03-test-report.md
  - name: implement (slice 2 — cookie import)
    completed: 2026-07-11T20:05:00Z
    artifact: >
      infrastructure/persistence/cookie_import.py (import_cookies) +
      cli/commands.py (booksaver auth import <file>) +
      monitor/session_manager.py + monitor/search_check_job.py (re-import
      hints in warnings/failure detail) + domain/check_result.py
      (session_mode field) + application/savings_pipeline.py (public-rate
      alert label) + runbook §11 + README Telegram-bot section
  - name: test (slice 2)
    completed: 2026-07-11T20:10:00Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 007-agentic-escalation
enables_bolts: []
requires_units:
  - 001-telegram-bot-gateway
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 4
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 012-vps-deployment

## Overview

The unit that makes BookSaver runnable unattended on an owner-operated VPS, in two slices.
Slice 1 covers US-034 in full (Dockerfile + systemd + ops runbook) and the **logged-out-checks
core** of US-035: the search journey runs cleanly with no saved Booking.com session, and
`AUTH_REQUIRED`-class failures are structurally impossible in that mode. Slice 2 completes US-035:
`booksaver auth import <file>` loads cookies exported from the user's own browser (Playwright-
native or common browser-extension export shapes), storing them with the same care as a headed-
login session; expiry falls back to logged-out mode with an explicit re-import hint rather than
silent price degradation; logged-out savings alerts are labeled as public rates.

## Objective

A fresh VPS reaches a running, unattended BookSaver container/service via one documented command
path, scheduled checks succeed without ever requiring the impossible-on-a-VPS headed
`booksaver auth` step, and an operator who wants member/Genius-rate accuracy on that same VPS has
a documented, secure cookie-import path to get it.

## Stories Included

- **US-034**: Deploy daemon and bot on a VPS (Must) — **complete**
- **US-035**: Logged-out checks with optional cookie import (Must: deployment / Should: cookie
  import) — **complete (both slices)**

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ✅ **1. Domain Model**: Complete → ddd-01-domain-model.md
- ✅ **2. Technical Design**: Complete → ddd-02-technical-design.md
- ✅ **3. Implement**: Complete → slice 1: SessionMode + logged-out journey gating +
  Dockerfile/compose/systemd + runbook; slice 2: cookie-import parsing/validation/storage,
  `booksaver auth import`, re-import hints, public-rate alert labeling
- ✅ **4. Test**: Complete → ddd-03-test-report.md (609/609; 36 new across both slices)

No ADR-analysis stage was needed: this bolt reuses existing ADRs (ADR-005 foreground daemon,
ADR-002 env-var secrets, ADR-018 self-hosted) without introducing a new architecturally
significant decision. The base-image choice (`python:3.12-slim` + explicit
`playwright install --with-deps chromium` over Microsoft's prebuilt Playwright image) is recorded
as a documented, reversible choice in the Dockerfile header and the runbook rather than a
standalone ADR.

## Dependencies

### Requires
- Bolt 007 (search journey + failure-code vocabulary this bolt gates `AUTH_REQUIRED` within)

### Requires (unit-level)
- Unit 001 `telegram-bot-gateway` for the `/status` surface the runbook references (US-036
  shipped there; `/status` doesn't yet render session mode explicitly, but
  `SessionManager.current_mode()` is available for it to call)

### Enables
- Real unattended VPS operation, with or without member-rate accuracy via cookie import

## Success Criteria

- [x] Journey with no session file runs cleanly and can succeed with public prices
- [x] `AUTH_REQUIRED` cannot be classified while running logged out (`SearchJourney` gate)
- [x] Authenticated-mode behavior (cookie restore, AUTH_REQUIRED classification, reauth flagging)
      is unchanged when a session file exists
- [x] Session mode is exposed via a small, side-effect-free accessor
      (`SessionManager.current_mode() -> SessionMode`) for a future `/status` command to consume
- [x] `Dockerfile` + `docker-compose.yml` + `deploy/booksaver.service` + `.dockerignore` present,
      reviewed line-by-line (Docker daemon unavailable in this environment — build/run untested,
      flagged in the test report)
- [x] Ops runbook covers provisioning, install, secrets, config, first-run, upgrade, backup,
      logs, the VPS-IP smoke test, the fallback ladder, and cookie import
- [x] README + `docs/DISCLAIMER.md` cover the "not affiliated, ToS risk is the operator's,
      no public bot mode" disclaimer, plus a Telegram-bot feature summary
- [x] Cookie-import CLI command (`booksaver auth import <file>`), validated storage (0600, never
      logs cookie values), expiry → re-import prompt, and public-rate alert labeling — all
      implemented and tested in slice 2

## Notes

- Coordination, slice 1: ran alongside two other in-flight workers (Telegram gateway/daemon/CLI
  owner; SQLite schema/repositories owner). Touched only `monitor/session_manager.py`,
  `monitor/search_journey.py`, `monitor/search_check_job.py`, `domain/session.py`, and new
  deployment/docs/test files — no daemon, CLI, schema, or repository files were changed.
- No DB schema change (slice 1 or 2): session-mode annotation on a logged-out successful check
  stayed logging-only through slice 1; slice 2 threads it as an **unpersisted** `CheckResult`
  field (`session_mode`, see its docstring in `domain/check_result.py`) that only needs to survive
  the in-memory hop from `run_all_active()` to `SavingsPipeline.process()` within one scheduler
  tick — no `check_history`/`check_traces` column, no migration, no schema-owner coordination
  needed.
- Coordination, slice 2: ran alongside a parallel worker on bolt 011 (Telegram rebook gate),
  scoped to stay out of `infrastructure/telegram/`, rebook code, and `[telegram_bot]` config
  parsing. Slice 2 touched `cli/commands.py` only in the `auth` parser/handler (new
  `cmd_auth_import` + `import` subparser), plus `infrastructure/persistence/cookie_import.py`
  (new), `domain/check_result.py`, `application/savings_pipeline.py`,
  `monitor/session_manager.py`, and `monitor/search_check_job.py` — no telegram/rebook files.
- No new runtime dependency in either slice: `SessionMode` is a plain domain enum;
  `cookie_import.py` uses only stdlib `json`/`dataclasses`/`datetime`; Docker/systemd/runbook add
  no Python dependency.
