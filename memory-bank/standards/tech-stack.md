# Tech Stack Standards

## Project Type

BookSaver Agent is a local-first Python daemon / CLI-style tool. It is not a hosted web app, frontend/backend split, SaaS product, or multi-tenant service.

## Current State

All 4 MVP units (bolts 001–005) plus intent 002's agentic search monitor (bolts 006–007)
are implemented. The stack below is decided and in use; each choice is recorded as an ADR
(see `standards/decision-index.md`).

## Runtime Stack (decided)

- **Language**: Python 3.11+ minimum, stdlib-first (ADR-003).
- **Runtime shape**: single local foreground daemon (`booksaver run`, ADR-005) with a `threading.Event` interval scheduler (ADR-006), plus CLI entry points.
- **Persistence**: SQLite via stdlib `sqlite3`, one file under the user's data directory, versioned migrations, currently schema v6 (ADR-001; v5 occupancy + extraction_method rebuild, v6 check_traces). Session cookies live in a per-platform JSON file (ADR-010).
- **Config**: `config.toml` via stdlib `tomllib`; secrets exclusively from environment variables (ADR-002).
- **Browser automation**: Playwright + bundled Chromium, synchronous API (ADR-007, ADR-008). Requires `playwright install chromium` after pip install.
- **LLM integration**: official `anthropic` SDK, default model `claude-haiku-4-5`, key from `BOOKSAVER_LLM_API_KEY` only; degrades to DOM-only extraction without a key (ADR-009). Two roles: offer extraction/judgment on the property page, and the browser-agent brain — a plain tool-use loop, no agent frameworks (ADR-016), tiered text→screenshot observations (ADR-015), hard `[agent]` config caps with adaptive budgeting named as future work (ADR-017).
- **Notifications**: stdlib `smtplib` (STARTTLS) for email, stdlib `urllib` against the Telegram Bot API (ADR-011); no BookSaver cloud relay.
- **Rebook safety**: guided final click — automation navigates, the human performs Booking.com's destructive click (ADR-012).

## Dependency Policy

Third-party runtime dependencies are limited to `playwright` and `anthropic`. Add a new one only when the stdlib genuinely cannot satisfy the need, and record the decision as an ADR (ADR-003).
