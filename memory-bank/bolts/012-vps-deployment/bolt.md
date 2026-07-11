---
id: 012-vps-deployment
unit: 005-vps-deployment
intent: 003-telegram-interface
type: ddd-construction-bolt
status: in_progress
stories:
  - 001-deploy-on-vps
  - 002-logged-out-checks-and-cookie-import
created: 2026-07-11T17:30:00Z
started: 2026-07-11T17:30:00Z
completed: null
current_stage: implement
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

First slice of the unit that makes BookSaver runnable unattended on an owner-operated VPS. This
slice covers US-034 in full (Dockerfile + systemd + ops runbook) and the **logged-out-checks
core** of US-035: the search journey runs cleanly with no saved Booking.com session, and
`AUTH_REQUIRED`-class failures are structurally impossible in that mode. The **cookie-import**
half of US-035 (exporting/loading member-rate cookies) is a later slice of this same bolt and is
explicitly out of scope here.

## Objective

A fresh VPS reaches a running, unattended BookSaver container/service via one documented command
path, and scheduled checks succeed without ever requiring the impossible-on-a-VPS headed
`booksaver auth` step.

## Stories Included

- **US-034**: Deploy daemon and bot on a VPS (Must) — **complete this bolt**
- **US-035**: Logged-out checks with optional cookie import (Must: deployment / Should: cookie
  import) — **logged-out core complete this bolt; cookie import pending a later slice**

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ✅ **1. Domain Model**: Complete → ddd-01-domain-model.md
- ✅ **2. Technical Design**: Complete → ddd-02-technical-design.md
- ✅ **3. Implement**: Complete (this slice) → SessionMode + logged-out journey gating +
  Dockerfile/compose/systemd + runbook
- ✅ **4. Test**: Complete (this slice) → ddd-03-test-report.md (367/367; 7 new)

No ADR-analysis stage was needed: this slice reuses existing ADRs (ADR-005 foreground daemon,
ADR-002 env-var secrets, ADR-018 self-hosted) without introducing a new architecturally
significant decision. The base-image choice (`python:3.12-slim` + explicit
`playwright install --with-deps chromium` over Microsoft's prebuilt Playwright image) is recorded
as a documented, reversible choice in the Dockerfile header and the runbook rather than a
standalone ADR.

## Dependencies

### Requires
- Bolt 007 (search journey + failure-code vocabulary this slice gates `AUTH_REQUIRED` within)

### Requires (unit-level, not blocking this slice)
- Unit 001 `telegram-bot-gateway` for the `/status` surface the runbook references as a TODO
  follow-up (US-036 ships there, per the unit brief)

### Enables
- Real unattended VPS operation once cookie import (US-035 remainder) lands

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
      logs, the VPS-IP smoke test, and the fallback ladder
- [x] README + `docs/DISCLAIMER.md` cover the "not affiliated, ToS risk is the operator's,
      no public bot mode" disclaimer
- [ ] Cookie-import CLI command, storage, and `/status` wiring — **deferred to the next slice**

## Notes

- Coordination: this bolt ran alongside two other in-flight workers (Telegram gateway/daemon/CLI
  owner; SQLite schema/repositories owner). This slice touched only
  `monitor/session_manager.py`, `monitor/search_journey.py`, `monitor/search_check_job.py`,
  `domain/session.py`, and new deployment/docs/test files — no daemon, CLI, schema, or repository
  files were changed.
- No DB schema change: session-mode annotation on a logged-out successful check is logging-only
  (`search_check_job.py`), not a new `CheckResult`/persistence field, since the schema is owned by
  another in-flight worker.
- No new runtime dependency: `SessionMode` is a plain domain enum; Docker/systemd/runbook add no
  Python dependency.
