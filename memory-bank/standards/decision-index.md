---
last_updated: 2026-07-19T02:39:40Z
total_decisions: 22
---

# Decision Index

This index tracks all Architecture Decision Records (ADRs) created during Construction bolts.
Use this to find relevant prior decisions when working on related features.

## How to Use

**For Agents**: Scan the "Read when" fields below to identify decisions relevant to your current task. Before implementing new features, check if existing ADRs constrain or guide your approach. Load the full ADR for matching entries.

**For Humans**: Browse decisions chronologically or search for keywords. Each entry links to the full ADR with complete context, alternatives considered, and consequences.

---

## Decisions

### ADR-022: Fixed invite-first admission for non-owner Telegram users
- **Status**: accepted
- **Date**: 2026-07-19T02:39:40Z
- **Bolt**: 021-invite-first-access (invite-first-access)
- **Path**: `bolts/021-invite-first-access/adr-022-fixed-invite-first-admission.md`
- **Summary**: The owner remains the sole administrator, while every non-owner is admitted only as an
  active known user or by redeeming one single-use invite. Runtime mode controls are removed; absent
  and legacy `owner`/`invite` config values normalize to fixed invite-first behavior, while
  public/open/unknown values remain invalid. Numeric Telegram IDs remain authoritative and optional
  usernames are display-only.
- **Read when**: Changing Telegram admission, invite redemption, access configuration, admin controls,
  username identity metadata, or revoked-user refusal behavior.

### ADR-021: One coordinator serializes scheduled and on-demand checks
- **Status**: accepted
- **Date**: 2026-07-18
- **Bolt**: 019-on-demand-check-orchestration (on-demand-check-orchestration)
- **Path**: `bolts/019-on-demand-check-orchestration/adr-021-single-check-coordinator.md`
- **Summary**: Scheduler ticks and Telegram `/checknow` requests share one non-blocking browser gate,
  one monitoring/savings pipeline, and thread-safe daily check/actual-LLM counters. Busy work is
  rejected rather than queued; daily LLM exhaustion degrades to scripted/DOM-only monitoring.
- **Read when**: Adding a check trigger, changing browser concurrency, modifying daily user limits,
  reporting LLM usage, or changing daemon shutdown behavior.

### ADR-020: Query-driven entry preserves the verified customer search
- **Status**: accepted
- **Date**: 2026-07-18
- **Bolt**: 014-production-reliability (production-reliability)
- **Path**: `bolts/014-production-reliability/adr-020-query-driven-search-entry.md`
- **Summary**: Production traces showed homepage form recovery consumed the shared check budget even though navigation used an independently constructed Booking.com results query. Checks now enter through that persisted-data query, while exact result selection, fresh property navigation, context verification, room-rate extraction, and guarded downstream LLM recovery remain mandatory.
- **Read when**: Working on search entry, journey step ordering, Booking.com results URLs, agent budget allocation, or reconsidering homepage form automation versus direct property links.

### ADR-019: Fernet (via `cryptography`) for personal-key encryption at rest
- **Status**: accepted
- **Date**: 2026-07-11
- **Bolt**: 009-user-access-and-keys (user-access-and-keys)
- **Path**: `bolts/009-user-access-and-keys/adr-019-fernet-user-key-encryption.md`
- **Summary**: Invited users' optional personal Anthropic keys (`/setkey`, hybrid billing) are encrypted at rest in `users.encrypted_key` with Fernet, keyed by `BOOKSAVER_SECRET_KEY` (env var, never config/git). Protects the DB file and its backups from exfiltration; explicitly does not protect against a fully compromised host (env-var trust boundary, same as every other secret in this project). Rejected: plaintext+chmod alone, stdlib obfuscation, OS keyring (headless VPS friction), per-user derived keys (no real safety gain, complicates rotation).
- **Read when**: Touching `users.encrypted_key`, the `/setkey`/`/deletekey` flow, `LLMClientFactory` per-user key resolution, or writing/updating the VPS deployment runbook's secrets section.

### ADR-018: Self-hosted deployment amends "local-only" — owner-operated laptop or VPS
- **Status**: accepted
- **Date**: 2026-07-11
- **Bolt**: 008-telegram-bot-gateway (telegram-bot-gateway)
- **Path**: `bolts/008-telegram-bot-gateway/adr-018-self-hosted-deployment.md`
- **Summary**: The MVP "local-only" constraint (US-013) is amended to "self-hosted, owner-operated": the daemon may run on the user's laptop OR an owner-operated VPS. Still no BookSaver-hosted cloud backend, no third-party data sharing; laptop single-user mode remains fully supported. Telegram access stays owner/invite only — no public bot mode.
- **Read when**: Working on deployment artifacts, the Telegram gateway, multi-user features, or anything that reads the "local-only" product constraint.

### ADR-017: Hard per-check cost caps now; adaptive budgeting is named future work
- **Status**: accepted
- **Date**: 2026-07-06
- **Bolt**: 007-agentic-escalation (agentic-escalation)
- **Path**: `bolts/007-agentic-escalation/adr-017-hard-caps-now-adaptive-later.md`
- **Summary**: `[agent]` config caps per check — max_steps 15 (screenshot turns ×2), max_llm_calls 20 (shared pool with extraction), check_timeout_seconds 180. Breach → `BUDGET_EXCEEDED`, daemon continues. Documented as the deliberately simple version; adaptive budgeting (per-day budgets, backoff, model downshift) is named future work.
- **Read when**: Touching agent/LLM cost controls, adding LLM calls to the check path, tuning cap defaults, or picking up the adaptive-budgeting follow-up.

### ADR-016: Bounded action vocabulary via SDK tool-use, guarded at the adapter
- **Status**: accepted
- **Date**: 2026-07-06
- **Bolt**: 007-agentic-escalation (agentic-escalation)
- **Path**: `bolts/007-agentic-escalation/adr-016-bounded-action-vocabulary.md`
- **Summary**: Agent acts only via click/fill/select/scroll/extract/request_screenshot/give_up on observation-enumerated element refs — no computer-use API, no model CSS/JS, no agent frameworks. ActionGuard (reserve/cancel/checkout/payment denylist) enforced at the adapter boundary + post-action URL check; safety never depends on the prompt.
- **Read when**: Modifying the agent loop or its tools, the ActionGuard rules, considering computer-use, or any change that lets a model influence browser actions.

### ADR-015: Tiered agent observations — text/DOM first, screenshot on demand
- **Status**: accepted
- **Date**: 2026-07-06
- **Bolt**: 007-agentic-escalation (agentic-escalation)
- **Path**: `bolts/007-agentic-escalation/adr-015-tiered-agent-observations.md`
- **Summary**: Tier 1 = URL/title/bounded text + enumerated interactive elements; screenshot attaches only on explicit request or after two consecutive failed actions, and such turns cost double budget. Vision is a deliberate spend, not the default.
- **Read when**: Changing agent observations, element enumeration, screenshot handling, or budget accounting per turn.

### ADR-014: Occupancy is a required registration field — no silent default
- **Status**: accepted
- **Date**: 2026-07-05
- **Bolt**: 006-search-journey-monitor (search-journey-monitor)
- **Path**: `bolts/006-search-journey-monitor/adr-014-occupancy-required-no-default.md`
- **Summary**: Search prices depend on party size, so `Occupancy(adults, children, rooms)` is required at registration; legacy bookings migrate to an explicit occupancy-missing state whose checks fail with `OCCUPANCY_MISSING` until `bookings set-occupancy` backfills them. Never a silent 2-adult guess.
- **Read when**: Touching registration, the bookings schema, search-query construction, or considering defaults for any user-specific search parameter.

### ADR-013: Full search journey replaces the manage page as the sole price source
- **Status**: amended by ADR-020
- **Date**: 2026-07-05
- **Bolt**: 006-search-journey-monitor (search-journey-monitor)
- **Path**: `bolts/006-search-journey-monitor/adr-013-search-journey-price-source.md`
- **Summary**: Live prices come exclusively from Booking.com's customer search journey (results query → exact property result → verified property → room table); `myreservations.html`, direct registered-property deep links, and result-card headline prices are never price sources. ADR-020 replaces the original homepage form entry with persisted-data results navigation while retaining downstream LLM seams.
- **Read when**: Working on the price monitor, journey steps, navigation failure codes, bot-wall handling, or reconsidering deep-linking/manage-page extraction.

### ADR-012: Guided final click — MVP does not automate the destructive button press
- **Status**: accepted
- **Date**: 2026-07-05
- **Bolt**: 005-guided-rebook (guided-rebook)
- **Path**: `bolts/005-guided-rebook/adr-012-guided-final-click.md`
- **Summary**: After each explicit confirmation the browser opens the correct cancel/rebook page; the human performs Booking.com's final click. State machine, gates, and audit trail are fully automated; the irreversible action is not. Strongest reading of "no autonomous cancel or purchase".
- **Read when**: Working on the rebook flow, considering automating final cancel/purchase clicks, or extending the RebookSession state machine.

### ADR-011: Stdlib-only notification transports (smtplib + urllib Telegram Bot API)
- **Status**: accepted
- **Date**: 2026-07-05
- **Bolt**: 004-savings-detection-notifications (savings-detection-notifications)
- **Path**: `bolts/004-savings-detection-notifications/adr-011-stdlib-notification-transports.md`
- **Summary**: Email via stdlib smtplib (STARTTLS), Telegram via one urllib POST to the Bot API. No requests/python-telegram-bot deps; Notifier port isolates the choice for the future interactive-bot direction.
- **Read when**: Adding/altering notification channels, SMTP/Telegram config fields, or considering an interactive Telegram bot interface.

### ADR-010: JSON file (not SQLite) for Booking.com session cookies
- **Status**: accepted
- **Date**: 2026-07-05
- **Bolt**: 003-booking-com-price-monitor (booking-com-price-monitor)
- **Path**: `bolts/003-booking-com-price-monitor/adr-010-json-session-file.md`
- **Summary**: Session cookies live in `{data_directory}/session_booking_com.json` (0600), matching Playwright's native cookie JSON shape. One file per platform; delete-to-logout; volatile auth material stays out of the booking DB.
- **Read when**: Working on session persistence, reauth flows, Unit 4 browser reuse, or adding a second platform's session storage.

### ADR-009: Anthropic SDK with a small default model for LLM extraction
- **Status**: accepted
- **Date**: 2026-07-05
- **Bolt**: 003-booking-com-price-monitor (booking-com-price-monitor)
- **Path**: `bolts/003-booking-com-price-monitor/adr-009-anthropic-sdk-llm-extraction.md`
- **Summary**: Official `anthropic` SDK, default model `claude-haiku-4-5` (config-overridable), key from `BOOKSAVER_LLM_API_KEY` only. Missing key degrades to DOM-only mode, never crashes.
- **Read when**: Touching LLM extraction, changing the extraction prompt or model, handling LLM errors, or adding another LLM provider adapter.

### ADR-008: Synchronous Playwright API in the scheduler loop
- **Status**: accepted
- **Date**: 2026-07-05
- **Bolt**: 003-booking-com-price-monitor (booking-com-price-monitor)
- **Path**: `bolts/003-booking-com-price-monitor/adr-008-sync-playwright-api.md`
- **Summary**: `playwright.sync_api` — checks run sequentially in the synchronous scheduler loop; no asyncio in the codebase. Port isolates the choice if concurrency is ever needed.
- **Read when**: Writing browser adapter code, considering concurrent checks, or tempted to introduce asyncio.

### ADR-007: Playwright for browser automation
- **Status**: accepted
- **Date**: 2026-07-05
- **Bolt**: 003-booking-com-price-monitor (booking-com-price-monitor)
- **Path**: `bolts/003-booking-com-price-monitor/adr-007-playwright-browser-automation.md`
- **Summary**: Playwright + bundled Chromium over Selenium/HTTP: first-class cookie export/import for sessions, headed mode for `booksaver auth`, headless for checks, auto-waiting for a dynamic site. Requires `playwright install chromium` post-install.
- **Read when**: Any browser automation work (Units 2 and 4), session login flows, navigation failure handling, or environment setup docs.

### ADR-006: threading.Event sleep loop as the scheduler mechanism
- **Status**: accepted
- **Date**: 2026-07-01
- **Bolt**: 002-core-local-data (core-local-data)
- **Path**: `bolts/002-core-local-data/adr-006-threading-event-scheduler.md`
- **Summary**: A `threading.Event.wait(timeout)` loop is used for the fixed-interval scheduler instead of `sched`, `time.sleep()`, or APScheduler. Wakes immediately on stop signal; no third-party dep; sufficient for a single fixed-interval job in MVP.
- **Read when**: Adding a new job to the scheduler; changing the check interval; considering APScheduler or cron-style scheduling for future units; implementing or testing clean daemon shutdown.

### ADR-005: Foreground-only daemon (no os.fork double-fork)
- **Status**: accepted
- **Date**: 2026-07-01
- **Bolt**: 002-core-local-data (core-local-data)
- **Path**: `bolts/002-core-local-data/adr-005-foreground-daemon.md`
- **Summary**: `booksaver run` blocks in the foreground; users background it with `&` or a systemd/launchd unit. No `os.fork()` double-fork or daemonization library. Simpler, debuggable, and compatible with OS service managers that expect foreground processes.
- **Read when**: Implementing `booksaver run`/`stop`; writing a systemd unit or launchd plist for auto-start; considering background daemonization for a future bolt.

### ADR-004: Hexagonal architecture with typing.Protocol repository interfaces
- **Status**: accepted
- **Date**: 2026-06-16
- **Bolt**: 001-core-local-data (core-local-data)
- **Path**: `bolts/001-core-local-data/adr-004-hexagonal-protocol-ports.md`
- **Summary**: Units 2–4 are declared consumers of Config, Booking, and LocalStore and must not couple to SQLite or the filesystem. Repository interfaces are defined as `typing.Protocol` classes in `application/ports.py`; SQLite and filesystem adapters live in `infrastructure/` and are injected at startup.
- **Read when**: Adding a new repository or data-access class; wiring a new unit that reads bookings, config, or check history; writing tests that need a fake in-memory store; adding a new driven adapter (e.g. a second persistence backend).

### ADR-003: Python 3.11+ baseline and standard-library-first core
- **Status**: accepted
- **Date**: 2026-06-16
- **Bolt**: 001-core-local-data (core-local-data)
- **Path**: `bolts/001-core-local-data/adr-003-python-311-stdlib-first.md`
- **Summary**: Python version and dependency philosophy were deferred as TBD in tech-stack.md. Require Python 3.11+ as the minimum runtime and prefer standard-library solutions, introducing a third-party runtime dependency only when the stdlib genuinely cannot satisfy a requirement.
- **Read when**: Considering adding a new third-party runtime dependency; choosing a Python version constraint; deciding whether to use stdlib vs a library for parsing, validation, HTTP, or date handling.

### ADR-002: TOML file + environment variables for config and secrets
- **Status**: accepted
- **Date**: 2026-06-16
- **Bolt**: 001-core-local-data (core-local-data)
- **Path**: `bolts/001-core-local-data/adr-002-toml-env-config.md`
- **Summary**: The daemon needs a user-editable local config file and a secret-handling approach that ensures secrets are never committed to git. Use `config.toml` (parsed with stdlib `tomllib`) for non-secret settings; secrets are read exclusively from environment variables and never written to any git-tracked file.
- **Read when**: Adding new config fields or sections; handling new secrets (API keys, tokens, passwords); implementing config loading or validation; working on notification or LLM credential handling in Units 2–3.

### ADR-001: SQLite as the local persistence store
- **Status**: accepted
- **Date**: 2026-06-16
- **Bolt**: 001-core-local-data (core-local-data)
- **Path**: `bolts/001-core-local-data/adr-001-sqlite-local-persistence.md`
- **Summary**: BookSaver Agent needs durable local storage with domain invariants enforced at the storage layer. Use SQLite (stdlib `sqlite3`) as the single local store — one file at `{data_directory}/booksaver.db` with UNIQUE and CHECK constraints matching domain rules.
- **Read when**: Extending the database schema (e.g. Unit 2 adding check_history columns); writing or modifying repository implementations; designing data migrations; working on persistence invariant tests.
