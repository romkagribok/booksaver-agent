# BookSaver Agent

![BookSaver Agent logo](assets/booksaver-logo.png)

BookSaver is a self-hosted Python agent that watches refundable Booking.com hotel
reservations for a cheaper equivalent room. It re-runs the search with the original dates and
occupancy, alerts the right user, and guides a rebook while leaving every cancellation, payment,
and final booking action to the human.

> [!WARNING]
> BookSaver is experimental personal-use software, not a hosted service. Booking.com UI changes,
> account state, and datacenter-IP controls can break live checks even when the test suite passes.
> Automated access may violate Booking.com's terms. Read the [full disclaimer](docs/DISCLAIMER.md)
> and validate the tool with your own refundable booking before relying on it.

## Current state

The implemented hotel-monitoring scope is complete: **103 in-scope stories, 31 construction bolts,
and 898 automated tests**. The current release includes:

- scripted Playwright searches with bounded LLM recovery when a page step changes;
- same-property, dates, occupancy, room-type, currency, and refundability checks;
- local SQLite history, redacted traces, savings alerts, and guided rebooking;
- a private Telegram interface with owner-issued, single-use invites and per-user isolation;
- encrypted, user-scoped Booking.com sessions and optional personal Anthropic keys;
- Docker/systemd deployment and an opt-in HTTPS `/connect` login flow for a trusted VPS;
- a noVNC-compatible, deny-by-default login viewer with native mobile-keyboard controls;
- immediate same-user `/connect` recovery after a viewer is closed or abandoned;
- complete user purge across SQLite and encrypted sessions, plus Booking.com-only login navigation.

It is ready for technical review and controlled self-hosting, not broad or untrusted-user
deployment. Open hardening work includes [journey verification](https://github.com/romkagribok/booksaver-agent/issues/4),
[failure alerts](https://github.com/romkagribok/booksaver-agent/issues/5), and stronger
[remote-login isolation](https://github.com/romkagribok/booksaver-agent/issues/6). Other open
issues are exploratory future capabilities, not missing parts of the current hotel-monitoring scope.

## How it works

1. You register a refundable hotel booking and its all-in baseline price.
2. On schedule or via `/checknow`, BookSaver opens a fresh authenticated mobile Chromium context
   and repeats the Booking.com search for the same stay and party.
3. Deterministic code drives the normal journey. If one step fails, an LLM browser agent may use a
   limited click/fill/select/scroll vocabulary. An adapter-level guard blocks reservation,
   checkout, payment, and cancellation destinations.
4. Only a cheaper, currency-aligned, still-refundable equivalent offer becomes a savings result.
5. Telegram or email reports the result. Rebooking uses explicit confirmations and hands the final
   action to the user's own device.

Every check is locally traceable with `booksaver checks trace <CHECK_ID>`.

## Recommended setup: private Telegram bot on your VPS

### Prerequisites

- a Linux host with Docker Compose v2, 2 GB RAM minimum, and a DNS name if `/connect` is enabled;
- a private Telegram bot token from BotFather and your numeric Telegram chat ID;
- an Anthropic API key for LLM extraction/recovery (without one, checks are scripted/DOM-only);
- acceptance of the trust boundary: the VPS runs the temporary login browser and must be under
  your control.

### Install

```bash
git clone https://github.com/romkagribok/booksaver-agent.git
cd booksaver-agent

cp .env.example .env
cp config.toml.example config.toml
chmod 600 .env config.toml
```

Fill in `.env`, set `owner_chat_id` in `config.toml`, and set the same HTTPS hostname in
`BOOKSAVER_AUTH_DOMAIN` and `remote_auth.public_url`. Then start and verify the stack:

```bash
docker compose --profile remote-auth up -d --build
docker compose ps
docker compose logs -f booksaver
```

In a private chat with the bot, send `/start`, then `/connect`, `/register`, and `/checknow`.
The first real Booking.com check is a required deployment test; VPS IPs can encounter bot walls.

The [VPS deployment runbook](memory-bank/operations/vps-deployment-runbook.md) covers DNS/TLS,
backups, upgrades, smoke testing, recovery cookie import, and the non-Docker systemd alternative.

## Local development and desktop operation

Python 3.11+ is required.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium

booksaver init
booksaver config validate
booksaver --help
```

`booksaver init` creates `~/.booksaver/config.toml` with mode `0600`. For a desktop operator,
enable the Telegram bot in that file, export the required `BOOKSAVER_*` values, and run
`booksaver run`. A headed `booksaver auth` login can be migrated to the Telegram-linked owner with
`booksaver auth migrate-legacy --telegram-user-id <ID>`. The normal VPS path is `/connect`.

Useful CLI commands include `bookings list`, `checks list`, `checks trace`, `savings list`,
`auth status|delete|import`, `rebook`, and `rebook-log`. Run any command with `--help` for its full
arguments.

## Data, LLM, and security boundaries

- Configuration, SQLite data, encrypted sessions, traces, and snapshots stay in the configured
  local data directory. Backups contain sensitive booking data and must be protected.
- Secrets are read from environment variables, never from committed configuration:
  `BOOKSAVER_TELEGRAM_BOT_TOKEN`, `BOOKSAVER_LLM_API_KEY`, `BOOKSAVER_SECRET_KEY`, and optional
  `BOOKSAVER_SMTP_PASSWORD`.
- BookSaver does not intentionally send cookies, passwords, MFA codes, or raw API keys to the LLM.
  When LLM features are enabled, it may send bounded rendered page text and, during escalation,
  screenshots to the configured Anthropic model. Rendered content can include account or booking
  details; use a provider/data policy you accept.
- `/connect` keeps credentials out of Telegram and BookSaver forms, but the browser executes on the
  VPS. A compromised root account could still observe login input. This is the known hardening
  boundary tracked in issue #6.
- Telegram access is owner/invite only. There is no public-bot mode and no BookSaver-operated
  backend.

## Development

```bash
python3 -m ruff check src tests
python3 -m mypy src
python3 -m pytest
```

Accepted requirements, decisions, and delivery history live in [`memory-bank/`](memory-bank/).
The installed specs.md AI-DLC framework lives in [`.specsmd/aidlc/`](.specsmd/aidlc/). Tool-specific
agent files are discovery adapters; the framework and memory bank are the authoritative sources.

## License and disclaimer

Released under the [MIT License](LICENSE). BookSaver is not affiliated with, endorsed by, or
sponsored by Booking.com or Booking Holdings Inc. See [`docs/DISCLAIMER.md`](docs/DISCLAIMER.md).
