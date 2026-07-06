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

## Safety posture

- No autonomous cancel or purchase — guided rebook always stops for explicit local confirmation, and the browser agent is guarded away from reservation-mutating pages.
- Local-only: config, SQLite data, session cookies, traces, and failure snapshots stay on your machine; LLM API calls carry page content only, never cookies or credentials.
- Secrets come exclusively from environment variables (`BOOKSAVER_LLM_API_KEY`, `BOOKSAVER_SMTP_PASSWORD`, `BOOKSAVER_TELEGRAM_BOT_TOKEN`).
