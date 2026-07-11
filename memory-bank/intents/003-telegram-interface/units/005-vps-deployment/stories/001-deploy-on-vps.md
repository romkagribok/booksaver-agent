---
id: US-034
status: complete
implemented: true
---

# US-034 Deploy daemon and bot on a VPS

**Intent:** `003-telegram-interface`
**Unit:** `005-vps-deployment`
**Status:** Complete
**Tag:** Phase 3

## Story

**As the** owner
**I want** a supported one-command deployment on a plain Linux VPS
**So that** BookSaver runs unattended and survives reboots

**Acceptance criteria**

- A Dockerfile builds an image with Python 3.11+, Playwright, and headless Chromium; `docker compose up -d` (or documented `docker run`) starts the daemon+bot with a persistent data volume
- A systemd unit alternative is provided for non-Docker hosts, with restart-on-failure
- Secrets (`BOOKSAVER_TELEGRAM_BOT_TOKEN`, owner `BOOKSAVER_LLM_API_KEY`, `BOOKSAVER_SECRET_KEY`, optional SMTP) enter via environment only — never baked into the image
- An ops runbook in `memory-bank/operations/` covers: provisioning (min 2 GB RAM), install, upgrade, backup of the data volume, log access, and the datacenter-IP bot-wall fallback options (lower frequency, residential proxy, home server)
- Kill-and-restart test: process is restarted automatically, no Telegram update lost or duplicated, schedule resumes

---
