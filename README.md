# BookSaver Agent

BookSaver Agent is a local-first Python daemon that monitors refundable Booking.com hotel bookings, detects price drops with browser automation and LLM-assisted page interpretation, notifies the user, and guides rebooking only with explicit human confirmation.

This project uses the official specs.md AI-DLC flow. Planning artifacts live in [`memory-bank/`](memory-bank/), and the installed specs.md agent definitions live in [`.specsmd/`](.specsmd/).

## How price checks work (Phase 2)

Booking.com never re-quotes an existing reservation on the My Bookings page, so BookSaver
finds savings the way a human would: on every scheduled check it **re-searches** the
registered property and dates (with your real party size) using your saved session,
opens the property page, and extracts the cheapest **equivalent, still-refundable** offer's
all-in bookable total. That total feeds the savings → notification → guided-rebook pipeline.

The search journey is scripted-first (deterministic Playwright). When Booking.com's UI
drifts and a scripted step fails, an **LLM browser agent** takes over just that step: it
sees a text/DOM observation (screenshot only when text isn't enough), acts through a
bounded action vocabulary (click / fill / select / scroll / give-up), and is hard-blocked
at the adapter level from ever touching reserve, checkout, payment, or cancellation flows.
Every check leaves a local step trace (`booksaver checks trace <check-id>`).

### Cost caps (deliberately simple — for now)

Each check runs under **hard caps** from `config.toml` `[agent]`: `max_steps` (default 15,
screenshot turns count double), `max_llm_calls` (default 20, shared between the agent and
offer extraction), and `check_timeout_seconds` (default 180). Breaching a cap fails the
check with `BUDGET_EXCEEDED` and the daemon moves on.

> **Note:** hard caps are the intentionally simple first version of cost control. If they
> prove too blunt in practice (checks failing on cap while making progress), the planned
> follow-up is *adaptive budgeting* — per-day token budgets across checks, backoff for
> bookings that repeatedly need escalation, and cheaper-model downshift for easy turns.
> See ADR-017 in `memory-bank/standards/decision-index.md`.

## Telegram bot

The primary interface is a Telegram bot you run yourself alongside the daemon (long-polling, no
inbound port needed). Access is **owner/invite only** — there is no public bot mode; strangers
self-host the repo instead of using yours. The owner registers bookings and gets alerts by default;
`/register` lets invited users add their own bookings from chat, each getting their own alert
routing and per-user daily check/LLM-call limits. LLM calls default to the owner's Anthropic key
(hybrid billing with per-user daily caps); `/setkey` lets a user opt into their own key instead
(encrypted at rest). A detected savings opportunity drives the same guided-rebook flow as the CLI,
but over Telegram: inline-keyboard confirmations at every step, and the final Booking.com
cancel/booking click is always handed off to your own device via a deep link — the bot itself never
completes it. See `memory-bank/intents/003-telegram-interface/requirements.md` for the full
requirements and `docs/DISCLAIMER.md` for what "no public bot mode" means in practice.

## Safety posture

- No autonomous cancel or purchase — guided rebook always stops for explicit local confirmation, and the browser agent is guarded away from reservation-mutating pages.
- Local-only: config, SQLite data, session cookies, traces, and failure snapshots stay on your machine; LLM API calls carry page content only, never cookies or credentials.
- Secrets come exclusively from environment variables (`BOOKSAVER_LLM_API_KEY`, `BOOKSAVER_SMTP_PASSWORD`, `BOOKSAVER_TELEGRAM_BOT_TOKEN`).

## Deployment

BookSaver can run on your laptop or on a VPS you operate (Docker or systemd) — see the
[VPS deployment runbook](memory-bank/operations/vps-deployment-runbook.md), the [`Dockerfile`](Dockerfile) /
[`docker-compose.yml`](docker-compose.yml), and [`deploy/booksaver.service`](deploy/booksaver.service).
On a display-less VPS, headed `booksaver auth` isn't possible, so scheduled checks default to
**logged-out mode** (public Booking.com prices, no saved session — labeled as such in savings
alerts) — see the runbook's "Logged-out checks" section for the VPS-IP validation smoke test and
fallback options. An optional `booksaver auth import <file>` loads cookies exported from your own
browser to unlock member/Genius-rate checks instead; see the runbook's "Cookie import" section.

## Disclaimer

This is an open-source, personal-use tool, **not affiliated with Booking.com**. Automated access to
Booking.com may violate its Terms of Service; running this tool (and how you run it) is entirely
your own responsibility. There is no public/multi-tenant bot mode by design. See
[`docs/DISCLAIMER.md`](docs/DISCLAIMER.md) for the full statement.
