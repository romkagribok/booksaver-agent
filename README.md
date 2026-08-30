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

The implemented hotel-monitoring scope is complete: **119 in-scope stories, 37 construction bolts,
and 1,038 automated tests**. The current release includes:

- scripted Playwright searches with bounded LLM recovery when a page step changes;
- same-property, dates, occupancy, room-type, currency, and refundability checks;
- local SQLite history, redacted traces, and savings alerts;
- automatic authenticated-account reservation discovery with visible eligibility reasons;
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

1. You connect your Booking.com account; BookSaver synchronizes positively observed reservations,
   preserves unseen saved rows when a refresh is partial or fails, and uses only current-run,
   upcoming, refundable observations for monitoring.
2. Three times per UTC day by default, BookSaver gives each user one randomized slot in a different
   broad part of the day. At each slot it synchronizes that user's account once, then opens a fresh
   authenticated mobile Chromium context for every eligible booking. `/checknow` remains available
   for an immediate check.
3. Price execution defaults to the `legacy` deterministic journey. The separately opt-in
   `owner_canary` price route uses local Stagehand semantic observation and, only when necessary, one
   guarded Anthropic computer-use episode in a fresh local Chromium profile. Every proposed action
   is code-authorized; reservation, checkout, payment, cancellation, credential, MFA/captcha,
   arbitrary navigation, shell, clipboard, upload, and download capabilities are absent.
4. Only a cheaper, currency-aligned, still-refundable equivalent offer becomes a savings result.
5. Telegram or email reports the result. You independently review and make any change in
   Booking.com; the next synchronization observes the updated account state.

Every check is locally traceable with `booksaver checks trace <CHECK_ID>`.
When guarded recovery assists account discovery, the local log includes a synchronization run ID;
inspect its content-free provider/call/token/action/timing audit with
`booksaver bookings trace <SYNC_RUN_ID>`.
Randomized slots are persisted locally, so restarts do not reroll or replay completed work. Send
`/status` to see your own next planned UTC slot.

The `[agent]` section uses a fixed Sonnet 5 primary and one measured Opus 5 escalation. Fable and
arbitrary model IDs are rejected. Model calls share persisted USD 1 per-browser-job and USD 10 per
deployment UTC-day ceilings; predictable outcomes such as a confirmed reconnect requirement use no
model call. The section also keeps the existing outer per-check limits (`max_steps`,
`max_llm_calls`, and `check_timeout_seconds`) and tighter recovery defaults:

```toml
primary_model = "claude-sonnet-5"
escalation_model = "claude-opus-5"
max_job_cost_usd = "1.00"
max_deployment_daily_cost_usd = "10.00"
reserve_opus_diagnostic_for_ambiguous_episode = true
max_recovery_calls_per_step = 4
recovery_timeout_seconds = 60
screenshot_after_no_progress = 2
max_semantic_action_executions = 2
```

Older config files remain valid and receive these defaults automatically. The inner limits cannot
expand the outer per-check or per-user daily LLM budgets.

Inventory and price use independent browser-executor routes. Agentic inventory is the default;
the agentic price executor remains disabled by default:

```toml
[agentic_browser]
routing = "legacy" # price: legacy | owner_canary | agentic
inventory_routing = "agentic" # inventory: legacy | agentic
disclosure_version = "anthropic-visible-booking-page-v1"
```

`inventory_routing = "agentic"` uses the pinned Browser Use classic agent for the user-initiated
`/bookings` refresh and Stagehand for the other read-only inventory triggers. Both run locally in a
fresh browser, receive only a closed set of code-guarded read-only actions, and use the deployment's
Anthropic key. BookSaver accepts only positively observed reservations from that run and never lets
model output mark an unseen saved reservation absent. Set it to `legacy` only as a
capability-specific rollback; this setting does not promote the price executor.

The Docker build installs the exact resolved runtime graph from `requirements.lock`; this is
intentional because Browser Use 0.11.13 has broad transitive dependency ranges. Telemetry, cloud
sync, external version checks, downloads, persistent screenshots, and stock Browser Use actions are
disabled by the BookSaver adapter.

For price execution, `owner_canary` is the only pre-qualification agentic mode and routes only the
deployment owner. The executor runs Stagehand 4.0.1 in-process against the installed Playwright
Chromium, injects encrypted Booking.com cookies through a code-owned local CDP connection, disables
cross-run caching and self-healing, and sends visible page content to Sonnet 5 using
`BOOKSAVER_LLM_API_KEY`. Stagehand semantic calls are the primary path; a screenshot-based
computer-use fallback receives at most six of the shared 15 actions. USD 1 per-check, USD 10
deployment-day, and 180-second limits remain hard.

The executor returns observations only. BookSaver still verifies property, dates, occupancy,
authentication, Genius evidence, currency, all-in totals, explicit refundability, room equivalence,
and the cheapest valid offer before any savings alert. Agentic failure is terminal for that check;
the legacy browser is a configured rollback route, not an automatic second attempt. Invited users
cannot receive agentic routing until the live promotion gate and their current versioned `/connect`
disclosure consent are recorded.

The owner governs that release entirely from the local VPS:

```bash
booksaver agentic status
booksaver agentic compare <CHECK_ID> --correct   # or --incorrect
booksaver agentic promote
booksaver agentic regress <MACHINE_CODE>
```

Promotion reads the persisted evidence itself and cannot be supplied a fabricated verdict. It
requires 30 owner checks over at least 14 days, ten correct manual comparisons, at least 95% valid
eligible observations, average cost at most USD 0.10, p95 cost at most USD 0.50, p95 duration at
most 180 seconds, fallback use at most 20%, zero critical violations, and explicit owner execution
of `promote`. During the 30-day rollback window, a critical violation or three consecutive eligible
failures automatically regresses routing to `legacy`. Offline fixtures qualify the adapter and
safety boundary; they do not substitute for this live owner evidence.

Model behavior can be measured without opening Booking.com or reading local sessions/database.
The explicit qualification command replays the packaged synthetic corpus ten times per fixture for
both approved profiles and requires at least nine correct runs per fixture with zero prohibited
executions. It reports aggregate correctness, safety, calls, actions, latency, token use, and exact
estimated cost without printing prompts or page content. Live execution requires an explicit cost
cap and is admitted call-by-call under the same deployment ceiling:

```bash
booksaver evaluate recovery --live --qualify --persist --max-cost-usd 10.00
booksaver evaluate qualification
```

It requires `BOOKSAVER_LLM_API_KEY`. Custom fixtures are exploratory only and cannot create a
recordable production qualification result.

If adaptive assistance indicates likely DOM drift, BookSaver correlates a content-free maintenance
incident and alerts only the configured owner. Inspect encrypted local evidence with
`booksaver incidents list` and `booksaver incidents inspect <INCIDENT_ID>`; bundles expire after
seven days and are never sent through Telegram.

## Recommended setup: private Telegram bot on your VPS

### Prerequisites

- a Linux host with Docker Compose v2, 2 GB RAM minimum, and a DNS name if `/connect` is enabled;
- a private Telegram bot token from BotFather and your numeric Telegram chat ID;
- an Anthropic API key for the default Browser Use/Stagehand inventory routes and LLM price extraction/recovery
  (without one, set `agentic_browser.inventory_routing = "legacy"` to use scripted inventory);
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
