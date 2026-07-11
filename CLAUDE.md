# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

BookSaver Agent is a planned **local-first Python daemon / CLI tool** that monitors a user's refundable
Booking.com hotel reservation, detects price drops via **browser automation + LLM-assisted page
interpretation**, notifies the user (email/Telegram), and offers a **guided rebook with mandatory human
confirmation**. It is explicitly *not* a web app, hosted service, or multi-tenant SaaS, uses *no* official
Booking.com API, and keeps all credentials, sessions, and data on the user's machine.

**Current state: MVP (intent 001, bolts 001–005) + Phase 2 agentic search monitor
(intent 002, bolts 006–007) complete — 20/22 stories, 360 tests. Intent 003
(Telegram as main interface, units 001–005, US-023–036) is validated and in
construction on branch `phase-3-telegram-interface` (bolts 008–012).**
Daemon + scheduler, savings detection with email/Telegram alerts, and the guided-rebook
confirmation state machine are implemented. **Phase 2 replaced the manage-page price
check**: live prices now come from a scripted full search journey (search → results →
verified property page → room table, using the booking's required occupancy), with an
LLM browser agent that takes over failed journey steps (tiered text→screenshot
observations, bounded action vocabulary, adapter-level guard against
reserve/checkout/cancel, hard cost caps, per-check traces). Unit 005-extensibility-future
is post-MVP. `project_type` is `cli-tool` (`memory-bank/project.yaml`).

## Build / Lint / Test Commands

```bash
# Install (editable, includes dev tools)
pip install -e ".[dev]"

# Lint + auto-fix
python3 -m ruff check src/ --fix
python3 -m ruff check src/         # must be clean before committing

# Type-check
python3 -m mypy src/

# Tests
python3 -m pytest

# One-time: install the browser Playwright drives
playwright install chromium

# Run CLI
python3 -m booksaver.cli <command>
# or, after pip install -e .:
booksaver <command>
```

CLI commands: `init`, `config validate|show`, `register` (requires `--adults`; `--children`,
`--rooms` optional), `bookings list`, `bookings set-occupancy <booking-id>` (backfill for
pre-v5 bookings), `run`, `stop`, `auth` (headed Booking.com login), `checks list <booking-id>`,
`checks trace <check-id>` (step/agent trace), `savings list`, `rebook <opportunity-id>`,
`rebook-log <session-id>`.

**Python 3.11+ required** (uses stdlib `tomllib`). Runtime deps are **playwright** (ADR-007)
and **anthropic** (ADR-009) only; everything else is stdlib-first (ADR-003) — notifications
use stdlib smtplib/urllib (ADR-011), and the browser agent is a plain anthropic tool-use
loop, no agent frameworks (ADR-016). Secrets come only from env vars:
`BOOKSAVER_LLM_API_KEY`, `BOOKSAVER_SMTP_PASSWORD`, `BOOKSAVER_TELEGRAM_BOT_TOKEN` (ADR-002).
See `memory-bank/standards/decision-index.md` for all 17 ADRs.

## This repo is driven by the specs.md AI-DLC flow

All planning happens through the **specs.md AI-DLC** framework (an AWS-derived, three-phase,
Domain-Driven methodology). The framework itself is installed under `.specsmd/aidlc/` (agents, skills,
templates, schema) and project artifacts live under `memory-bank/`. Work is done by invoking specialized
agents as slash commands, not by editing artifacts ad hoc:

| Command | Phase | Role |
|---------|-------|------|
| `/specsmd-master-agent` | — | **Start here.** Orchestrator: routes requests, analyzes state, answers methodology questions |
| `/specsmd-inception-agent` | Inception | Requirements, stories, system context, unit decomposition, bolt planning |
| `/specsmd-construction-agent` | Construction | Execute bolts through DDD stages (domain → technical design → implement → test) |
| `/specsmd-operations-agent` | Operations | Build, deploy, verify, monitor |

These are duplicated into `.claude/commands/`, `.claude/agents/`, and `.cursor/commands/` by the
installer — edit agent behavior in `.specsmd/aidlc/`, not the copies.

**Hierarchy:** Intent (a capability) → Unit (independently buildable component) → Story. A **Bolt** is a
time-boxed execution session scoped to a Unit. Agents are **stateless** — they read context fresh from
`memory-bank/` each invocation, so artifacts must be saved after each step. Humans validate at every
checkpoint (after requirements, decomposition, each bolt stage, before deploy).

## Memory bank layout and conventions

`.specsmd/aidlc/memory-bank.yaml` is the **authoritative schema** — read it before placing or renaming
artifacts. Key paths:

- `memory-bank/intents/{NNN}-{intent}/` — `requirements.md`, `system-context.md`, `units.md`
- `.../units/{UUU}-{unit}/` — `unit-brief.md`, `construction-log.md`, `stories/{SSS}-{slug}.md`
- `memory-bank/bolts/{BBB}-{unit}/` — `bolt.md` + DDD stage artifacts
- `memory-bank/standards/` — project standards (see below)
- `memory-bank/story-index.md` — single-file global index of all stories

Hard conventions enforced by the schema: **3-digit zero-padded prefixes** on intents/units/stories/bolts,
**kebab-case** names derived from folder/file names (no frontmatter name prefixes), and **ISO-8601
timestamps with time + timezone** (`YYYY-MM-DDTHH:MM:SSZ`) on every date field — never date-only. Keep
`story-index.md` consistent when stories change; it asserts all 16 stories are assigned exactly once.

## Standards are the source of truth for product + tech constraints

`memory-bank/standards/` files are loaded as context by every agent — treat them as binding when
designing or coding:

- `system-architecture.md` — single-process local daemon; modular components
  (`LocalConfig → Scheduler → BookingComMonitor → {BrowserAutomation, LLMClient, LocalPersistence} →
  SavingsDetection → {Notifications, GuidedRebook}`), not distributed services.
- `tech-stack.md` — Python 3.11+ stdlib-first; SQLite persistence; Playwright (sync) browser
  automation; anthropic SDK for extraction; stdlib smtplib/urllib notifications. All decided —
  see the ADRs in `standards/decision-index.md`.
- `coding-standards.md` — explicit domain types for bookings/prices/check-results/savings/rebook events;
  keep browser automation, LLM extraction, savings evaluation, notification, and rebook-confirmation
  logic in separate module boundaries; first test coverage targets config validation, persistence
  invariants, savings equivalence rules, and confirmation gates.

## Intents

### `001-booksaver-agent-mvp` — complete (except post-MVP unit 5)

1. `001-core-local-data` — ✅ complete (bolts 001+002): config, registration, SQLite, daemon/scheduler
2. `002-booking-com-price-monitor` — ✅ complete (bolt 003): session, browser checks, LLM extraction, failure handling. **Superseded as price source by intent 002** (manage page kept for session validation only, ADR-013)
3. `003-savings-detection-notifications` — ✅ complete (bolt 004): equivalence gate, price rule, email + Telegram
4. `004-guided-rebook` — ✅ complete (bolt 005): explicit intent, confirmation state machine, audit trail
5. `005-extensibility-future` — pluggable second platform / non-hotel types (post-MVP only)

### `002-agentic-search-monitor` — complete

1. `001-search-journey-monitor` — ✅ complete (bolt 006): required `Occupancy` at registration
   (ADR-014, schema v5 migration + CLI backfill), scripted full search journey with named
   `JourneyStep` seams (ADR-013), equivalent-offer extraction (DOM heuristics + LLM
   `extract_offers`), `select_offer` exclusion rules, new failure codes
2. `002-agentic-escalation` — ✅ complete (bolt 007): `BrowserAgent` loop with tiered
   observations (ADR-015), bounded tool-use action vocabulary + adapter-level `ActionGuard`
   (ADR-016), hard `[agent]` config caps (ADR-017), `check_traces` (schema v6), rotated
   redacted failure snapshots, `checks list|trace` CLI

### `003-telegram-interface` — validated, in construction (bolts 008–012)

Telegram bot as the primary UI on an owner-operated VPS. Checkpoint 1 decisions (2026-07-11):
access modes `owner`/`invite` only (no public mode); hybrid LLM billing (owner key + per-user
daily caps by default, optional encrypted personal key via `/setkey`, Fernet/`cryptography`
approved); VPS-first deployment with an early Booking.com-journey smoke test from the VPS IP;
logged-out checks by default (headed auth impossible on a VPS); rebook confirmations via inline
keyboards with the final booking click handed off to the user's device via deep link.

1. `001-telegram-bot-gateway` — long-poll update loop thread + router + dialogs, read-only commands (bolt 008)
2. `002-user-access-and-keys` — schema v7 users table + scoping, access modes, key store (bolt 009)
3. `003-conversational-booking-ops` — `/register` dialog, per-user alert routing + limits (bolt 010)
4. `004-telegram-rebook-gate` — Telegram `ConfirmationGate` + device-handoff deep link (bolt 011)
5. `005-vps-deployment` — Dockerfile/systemd, ops runbook, logged-out sessions + cookie import (bolt 012)

## Product constraints to preserve in every design and code change

- **Booking.com hotels only** in MVP; reject other booking types with a clear message.
- **Refundable bookings only**; a cheaper offer must itself still be refundable to count as savings.
- **Equivalence = same property, same check-in/out dates, same room type**, still refundable.
- **No autonomous cancel or purchase** — guided rebook always requires an explicit local confirmation step.
- **Self-hosted only** (ADR-018 amends the MVP "local-only" wording): runs on the user's laptop or an
  owner-operated VPS; no outbound calls to any BookSaver-hosted backend; secrets never committed to git.
- **No public bot mode** — Telegram access is `owner`/`invite` only; strangers self-host the repo.

# Orchestration rules

- When you decompose a task into subtasks:
  - If a subtask has clear inputs and outputs and does not require global architectural changes, treat it as an **execution** task.
  - Execution tasks must be handled by Sonnet-backed subagents (e.g. `sonnet-worker`), not additional Fable instances.
- When you identify multiple independent execution tasks, spawn **multiple Sonnet subagents in parallel** rather than doing them sequentially.
- Keep all reasoning, plan updates, and cross-subtask coordination in this main Fable session.
- Do not spawn Fable subagents. Parallel work must use Sonnet workers.
