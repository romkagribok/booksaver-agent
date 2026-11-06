# BookSaver Agent

![BookSaver Agent logo](assets/booksaver-logo.png)

BookSaver is a self-hosted Python agent that watches refundable Booking.com hotel
reservations for a cheaper equivalent room. It re-runs the search with the original dates and
occupancy and alerts the right user. Reservation changes happen independently in Booking.com;
BookSaver never cancels, books, pays, or runs a rebooking workflow.

> [!WARNING]
> BookSaver is experimental personal-use software, not a hosted service. Booking.com UI changes,
> account state, and datacenter-IP controls can break live checks even when the test suite passes.
> Automated access may violate Booking.com's terms. Read the [full disclaimer](docs/DISCLAIMER.md)
> and validate the tool with your own refundable booking before relying on it.

## Current state

See the [story index](memory-bank/story-index.md) for delivery and qualification status and the
[decision index](memory-bank/standards/decision-index.md) for accepted architecture.
The implementation includes:

- bounded Browser Use browser execution with TypeSafe's Jev as the only model provider;
- same-property, dates, occupancy, room-type, currency, and refundability checks;
- local SQLite history, redacted traces, and savings alerts;
- automatic authenticated-account reservation discovery with visible eligibility reasons;
- a private Telegram interface with owner-issued, single-use invites and per-user isolation;
- encrypted, user-scoped Booking.com sessions;
- Docker/systemd deployment and an opt-in HTTPS `/connect` login flow for a trusted VPS;
- a noVNC-compatible, deny-by-default login viewer with native mobile-keyboard controls;
- immediate same-user `/connect` recovery after a viewer is closed or abandoned;
- complete user purge across SQLite and encrypted sessions, plus Booking.com-only login navigation.

Use the [issue tracker](https://github.com/romkagribok/booksaver-agent/issues) for current open
work. Qualification and live acceptance remain explicit gates in the lifecycle artifacts.

## How it works

1. You connect your Booking.com account; BookSaver synchronizes positively observed reservations,
   preserves unseen saved rows when a refresh is partial or fails, and uses only current-run,
   upcoming, refundable observations for monitoring.
2. Three times per UTC day by default, BookSaver gives each user one randomized slot in a different
   broad part of the day. At each slot it synchronizes that user's account once, then opens a fresh
   authenticated mobile Chromium context for every eligible booking. `/checknow` remains available
   for an immediate check.
3. Every price check runs the pinned local Browser Use classic agent in a fresh local Chromium
   profile, with TypeSafe's Jev as the model. Every physical action is code-authorized;
   reservation, checkout, payment, cancellation, credential, MFA/captcha, arbitrary navigation,
   shell, clipboard, upload, and download capabilities are absent.
4. Only a cheaper, currency-aligned, still-refundable equivalent offer becomes a savings result.
5. Telegram or email reports the result. You independently review and make any change in
   Booking.com; the next synchronization observes the updated account state.

Every check is locally traceable with `booksaver checks trace <CHECK_ID>`.

Agentic price traces include a versioned `price_validation` event for successful and rejected
observations. It records query/terminal rejection, all failed per-offer evidence checks, actual
room-match/selection outcomes, and bounded lexical room hints. Inspect `offers[].selection` for
room mismatch or other exclusions, and `offers[].evidence_rejections` for missing/conflicting
all-in, refundability, completeness, or currency evidence. Up to 20 offers are detailed; the total
and omitted counts are explicit. Room hints are recognized words, not semantic equivalence
claims; missing words mean unmentioned, not absent. Raw room labels, page text, screenshots,
refundability prose, and secrets are not added to these diagnostics. This instrumentation does
not change which offers are accepted or invoke additional models.
When guarded recovery assists account discovery, the local log includes a synchronization run ID;
inspect its content-free provider/call/token/action/timing audit with
`booksaver bookings trace <SYNC_RUN_ID>`.
Randomized slots are persisted locally, so restarts do not reroll or replay completed work. Send
`/status` to see your own next planned UTC slot.

TypeSafe's Jev (`BOOKSAVER_TYPESAFE_API_KEY`) is the only model provider and is required for
price checks and for the reservation-facts part of account syncs. The only `[agent]` setting is
`max_job_cost_usd` (USD 1.00 by default); other `[agent]` keys, `[extraction]`, `routing`, and
`inventory_routing` from older config files are ignored with one warning, and the files still
load. Every active user uses Jev:

```toml
[agentic_browser]
price_executor = "jev"
disclosure_version = "typesafe-visible-booking-page-v1"
```

The Docker build installs the exact resolved runtime graph from `requirements.lock`; this is
intentional because Browser Use 0.11.13 has broad transitive dependency ranges. Telemetry, cloud
sync, external version checks, downloads, persistent screenshots, and stock Browser Use actions are
disabled by the BookSaver adapter.

### Jev as the price method

`[agentic_browser] price_executor = "jev"` (ADR-056) runs Jev behind the provider-neutral port and
the validators below. Browser Use drives a fresh local Chromium, injects encrypted Booking.com
cookies through a code-owned local CDP connection, and exposes only guarded read-only
clicks/scrolls/keys/waits and typed submissions; BookSaver constructs the trusted search URL and
proves authentication independently. The executor returns observations only. BookSaver still
verifies property, dates, occupancy, authentication, Genius evidence, currency, all-in totals,
explicit refundability, room equivalence, and the cheapest valid offer before any savings alert,
and an executor failure is terminal for that check. Invited users always require current
versioned `/connect` disclosure consent.

The result is what check history, session refresh, and savings alerts are based on. Jev needs
`BOOKSAVER_TYPESAFE_API_KEY` and is bounded by the model pin, per-check call cap, and daily cost
cap in `[jev_comparison]`, whose `enabled` flag must stay false in this mode. Each run's provider
cost and a content-free diagnostic are kept in `jev_price_runs` (`booksaver comparison report`).

### Jev price comparison (paired mode)

`[jev_comparison] enabled = true` plus `BOOKSAVER_TYPESAFE_API_KEY` runs a second, independent
price method on every admitted manual and scheduled check: TypeSafe's Jev (`jev-1.13.0`, pinned)
only chooses among options BookSaver builds from the page (a guarded control to click, the
property heading, the room-name line, the whole-stay total, the stated cancellation and tax
terms), while BookSaver code parses every amount and applies the unchanged validators. No other
model is called in that method. Both methods start from the same session snapshot, run one after
the other in random order under the single browser lease, and the booking owner receives one
Telegram report with both results, timings, and AI costs. Only the existing method updates check
history, sessions, and savings alerts. `participants = "all"` includes invitees; their booking
page text is then sent to TypeSafe, so tell them first.

If adaptive assistance indicates likely DOM drift, BookSaver correlates a content-free maintenance
incident and alerts only the configured owner. Inspect encrypted local evidence with
`booksaver incidents list` and `booksaver incidents inspect <INCIDENT_ID>`; bundles expire after
seven days and are never sent through Telegram.

## Recommended setup: private Telegram bot on your VPS

### Prerequisites

- a Linux host with Docker Compose v2, 2 GB RAM minimum, and a DNS name if `/connect` is enabled;
- a private Telegram bot token from BotFather and your numeric Telegram chat ID;
- a TypeSafe API key (`BOOKSAVER_TYPESAFE_API_KEY`), required for price checks and account syncs;
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

In a private chat with the bot, send `/start`, then `/connect`. BookSaver discovers your
Booking.com reservations automatically. Use `/bookings` to refresh the account inventory and see
why any reservation is ineligible for price-drop checks. Bare `/checknow` immediately shows saved
caller-owned choices; selecting one runs a single fresh inventory verification and immediate price
check through the coordinator.
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
`booksaver run`. Connect each admitted user through `/connect`; `auth import` remains a scoped
break-glass recovery path.

Useful CLI commands include `bookings list`, `checks list`, `checks trace`, `savings list`,
and `auth status|delete|import`. Run any command with `--help` for its full arguments.

## Data, LLM, and security boundaries

- Configuration, SQLite data, encrypted sessions, traces, and snapshots stay in the configured
  local data directory. Backups contain sensitive booking data and must be protected.
- Secrets are read from environment variables, never from committed configuration:
  `BOOKSAVER_TELEGRAM_BOT_TOKEN`, `BOOKSAVER_TYPESAFE_API_KEY`, `BOOKSAVER_SECRET_KEY`, and
  optional `BOOKSAVER_SMTP_PASSWORD`.
- BookSaver does not intentionally send cookies, passwords, MFA codes, or raw API keys to the LLM.
  It sends bounded rendered page text to TypeSafe's Jev. Rendered content can include account or booking
  details; use a provider/data policy you accept.
- `/connect` keeps credentials out of Telegram and BookSaver forms, but the browser executes on the
  VPS. A compromised root account could still observe login input. This is the known hardening
  boundary tracked in issue #6.
- Telegram access is owner/invite only. There is no public-bot mode and no BookSaver-operated
  backend.

## Development

Install the Python development extras and existing Node validation dependencies before running
the repository quality gate:

```bash
python3 -m pip install -e ".[dev]"
npm ci
python3 -m ruff check src tests
python3 -m mypy src
python3 -m pytest
npm run test:aidlc-validator
npm run validate:aidlc
```

Accepted requirements, decisions, and delivery history live in [`memory-bank/`](memory-bank/).
The installed specs.md AI-DLC framework lives in [`.specsmd/aidlc/`](.specsmd/aidlc/). Tool-specific
agent files are discovery adapters; the framework and memory bank are the authoritative sources.

## License and disclaimer

Released under the [MIT License](LICENSE). BookSaver is not affiliated with, endorsed by, or
sponsored by Booking.com or Booking Holdings Inc. See [`docs/DISCLAIMER.md`](docs/DISCLAIMER.md).
