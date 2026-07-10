# Unit Brief: VPS Deployment

**Unit ID:** `005-vps-deployment`
**Intent:** `003-telegram-interface`
**Status:** Planned
**Build order:** 5

## Purpose

Make the daemon+bot run unattended on an owner-operated VPS: a Dockerfile (Playwright + headless
Chromium) and a systemd alternative, an ops runbook under `memory-bank/operations/`, a logged-out
session strategy (headed `booksaver auth` is impossible without a display — checks default to public
prices), and an optional cookie-import path for member/Genius rates. Operations-phase artifacts are
produced with the Operations agent.

## Dependencies on other units

| Unit | What this unit needs |
|------|----------------------|
| `001-telegram-bot-gateway` | `/status` health surface (deployable owner-only after Unit 1) |
| `003-conversational-booking-ops` | Full multi-user feature set for the shared deployment |
| intent-002 | Search journey must tolerate logged-out state (no `AUTH_REQUIRED` in logged-out mode) |

## Loose coupling / interfaces (design-level)

| Consumes | From |
|----------|------|
| Env vars: bot token, owner LLM key, `BOOKSAVER_SECRET_KEY` | deployment environment |
| Data directory volume (SQLite, traces, snapshots, keys) | host |

| Emits | To |
|-------|-----|
| Container image / systemd unit + runbook | `memory-bank/operations/` |
| Session-mode flag (logged-out vs imported cookies) per deployment | session manager |

## Recommended implementation order (within unit)

1. US-034 — Dockerfile + systemd unit + runbook (provision, secrets, restart policy, upgrade)
2. US-035 — cookie-import command (user exports cookies from own browser; validated then stored)
3. (US-036 `/status` ships in Unit 1; runbook references it)

## Completion criteria (unit-level)

- Fresh VPS to running bot in one documented command path.
- Scheduled checks succeed logged-out from the VPS; datacenter-IP bot-wall failures are recorded with
  distinct codes and covered in the runbook (fallbacks: lower frequency, residential proxy, home
  server).
- Restart policy proven: kill the process, daemon+bot recover, no duplicate Telegram updates.

---

## Story Files

- `US-034`
- `US-035`
