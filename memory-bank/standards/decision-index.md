---
last_updated: 2026-08-30T18:15:00Z
total_decisions: 41
---

# Decision Index

This index tracks all Architecture Decision Records (ADRs) created during Construction bolts.
Use this to find relevant prior decisions when working on related features.

## How to Use

**For Agents**: Scan the "Read when" fields below to identify decisions relevant to your current task. Before implementing new features, check if existing ADRs constrain or guide your approach. Load the full ADR for matching entries.

**For Humans**: Browse decisions chronologically or search for keywords. Each entry links to the full ADR with complete context, alternatives considered, and consequences.

---

## Decisions

### ADR-041: Trigger-specific local Browser Use execution for `/bookings`
- **Status**: accepted
- **Date**: 2026-08-30
- **Bolt**: 060-agentic-inventory-executor (agentic-inventory-executor)
- **Path**: `bolts/060-agentic-inventory-executor/adr-041-trigger-specific-browser-use-for-bookings.md`
- **Summary**: Route only Telegram `/bookings` through exactly pinned local Browser Use OSS behind
  the existing inventory port, with a closed BookSaver-owned tool registry, code-owned dialog
  rejection, existing limits, and no same-job fallback. Other inventory triggers and price paths
  remain unchanged.
- **Read when**: Changing Browser Use versions, `/bookings` executor selection, inventory trigger
  routing, Browser Use tools/dialogs/telemetry, provider SDK compatibility, or Stagehand coexistence.

### ADR-040: Separate destination observation from interaction authority
- **Status**: accepted
- **Date**: 2026-08-27
- **Bolt**: 056-agentic-inventory-executor (agentic-inventory-executor)
- **Path**: `bolts/056-agentic-inventory-executor/adr-040-separate-observation-from-interaction-authority.md`
- **Summary**: Exact inventory route/query admission blocked the first live Stagehand run before
  semantic extraction. Allow unfamiliar non-mutating HTTPS Booking.com destinations to be observed,
  but require task-specific inspected evidence for every interaction and log only sanitized route
  shape on rejection.
- **Read when**: Changing agentic inventory destinations, route classification, semantic or visual
  action guards, Booking.com redirect handling, unsafe destination terminals, or browser diagnostics.

### ADR-039: Capability-specific positive-only agentic inventory
- **Status**: accepted
- **Date**: 2026-08-26
- **Bolt**: 053-agentic-inventory-executor (agentic-inventory-executor)
- **Path**: `bolts/053-agentic-inventory-executor/adr-039-capability-specific-positive-only-agentic-inventory.md`
- **Summary**: Legacy inventory blocks price-canary evidence. Route a separate Stagehand inventory
  capability to every disclosed authorized user, reconcile only current-run positive observations,
  preserve unseen rows, and require a fresh receipt before price checking.
- **Read when**: Changing inventory browser execution, account synchronization completeness,
  current-run check admission, `/checknow` refresh orchestration, capability routing, or legacy
  inventory rollback.

### ADR-038: Owner-only canary, consented promotion, and rollback window
- **Status**: accepted
- **Date**: 2026-08-16
- **Bolt**: 052-agentic-browser-qualification (agentic-browser-qualification)
- **Path**: `bolts/052-agentic-browser-qualification/adr-038-owner-canary-promotion-and-rollback.md`
- **Summary**: Legacy stays default while an owner-only live canary proves safety, correctness,
  reliability, cost, and duration. Invited-user routing additionally requires explicit disclosure
  consent and owner promotion; regressions return to legacy during a 30-day rollback window.
- **Read when**: Changing agentic routing, qualification thresholds, canary records, invitee consent,
  promotion, rollback, or legacy price-path retirement.

### ADR-037: Local Stagehand with guarded Anthropic computer use
- **Status**: accepted
- **Date**: 2026-08-16
- **Bolt**: 051-local-agentic-price-executor (local-agentic-price-executor)
- **Path**: `bolts/051-local-agentic-price-executor/adr-037-local-stagehand-and-guarded-computer-use.md`
- **Summary**: Pin and run Stagehand locally for observe/guard/replay semantic execution and typed
  extraction, then allow one six-action Sonnet computer-use episode on the same transient browser.
  BookSaver executes and verifies every action; managed browsers and custom caches are excluded.
- **Read when**: Changing Stagehand, computer use, browser custody, semantic actions, screenshots,
  telemetry, provider tools, Chromium packaging, or action guards.

### ADR-036: Trusted control plane and provider-neutral browser executor port
- **Status**: accepted
- **Date**: 2026-08-16
- **Bolt**: 050-agentic-executor-control-plane (agentic-executor-control-plane)
- **Path**: `bolts/050-agentic-executor-control-plane/adr-036-trusted-control-plane-and-executor-port.md`
- **Summary**: Browser harnesses return only untrusted typed evidence through a provider-neutral port.
  BookSaver retains session custody and sole authority for validation, equivalence, savings,
  persistence, notifications, and transactions.
- **Read when**: Changing browser executor contracts, price evidence, session leases, routing,
  adapter replaceability, validation authority, or sensitive-data boundaries.

### ADR-035: Server-backed remote authentication verification
- **Status**: accepted
- **Date**: 2026-08-15
- **Bolt**: 048-dom-resilient-browser-workflows (dom-resilient-browser-workflows)
- **Path**: `bolts/048-dom-resilient-browser-workflows/adr-035-server-backed-remote-authentication-verification.md`
- **Summary**: Reservation DOM, visible URLs, cookie heuristics, and model output cannot prove a
  `/connect` login. Contract v2 accepts only the OAuth redirect or the exact empty `202` edge tuple
  as negative evidence, still requires two isolated exact signed-in probes, and binds one-use
  finalization to the exact verified cookie snapshot.
- **Read when**: Changing `/connect` success detection, remote browser cookies, server-session
  verification, authentication receipts, protected Booking endpoints, or login finalization.

### ADR-034: Owner-only encrypted DOM incident operations
- **Status**: accepted
- **Date**: 2026-08-13
- **Bolt**: 044-dom-drift-incident-operations (dom-drift-incident-operations)
- **Path**: `bolts/044-dom-drift-incident-operations/adr-034-owner-only-encrypted-dom-incident-operations.md`
- **Summary**: Maintenance-worthy assisted DOM outcomes need durable owner visibility without
  exposing page/account data. Correlate content-free fingerprints, notify only the owner after
  browser cleanup, and retain one sanitized encrypted local bundle for seven days.
- **Read when**: Changing DOM incident eligibility/correlation, owner alerts, diagnostics,
  screenshots, retention, user purge, incident CLI/status, or daemon maintenance workers.

### ADR-033: Semantic evidence and guarded popup adoption
- **Status**: accepted
- **Date**: 2026-08-13
- **Bolt**: 043-dom-resilient-browser-workflows (dom-resilient-browser-workflows)
- **Path**: `bolts/043-dom-resilient-browser-workflows/adr-033-semantic-evidence-and-guarded-popup-adoption.md`
- **Summary**: Legacy selectors cannot remain the sole verifier after a model finds changed safe
  controls. Accept only grounded positive semantic evidence under code-owned verification, adopt at
  most one guarded read-only popup, and preserve a canonical exact terminal diagnosis.
- **Read when**: Changing browser-agent postconditions, semantic model facts, search/inventory DOM
  recovery, popup handling, offer extraction, or terminal failure propagation.

### ADR-032: Protected-first page state and exhaustive DOM step registry
- **Status**: accepted
- **Date**: 2026-08-13
- **Bolt**: 042-dom-resilient-browser-workflows (dom-resilient-browser-workflows)
- **Path**: `bolts/042-dom-resilient-browser-workflows/adr-032-protected-first-page-state-and-dom-step-registry.md`
- **Summary**: Distributed DOM/auth heuristics can accept weak signed-in chrome and collapse exact
  model conclusions into generic failures. Register every production DOM step, classify protected
  states before weak chrome, and use adaptive models only for genuinely ambiguous current state.
- **Read when**: Changing authentication/session inference, remote auth capture, inventory/search
  page classification, DOM-step coverage, model-assisted classification, or exact browser failure
  mapping.

### ADR-031: Adaptive Sonnet/Opus routing and dollar admission
- **Status**: accepted
- **Date**: 2026-08-13
- **Bolt**: 041-adaptive-model-policy (adaptive-model-policy)
- **Path**: `bolts/041-adaptive-model-policy/adr-031-adaptive-sonnet-opus-routing-and-dollar-admission.md`
- **Summary**: Single-profile recovery and restart-reset call counters cannot replace an ineffective
  model or enforce approved dollar limits. Use a fixed Sonnet 5 primary and Opus 5 escalation only
  for ambiguous DOM work, short-circuit predictable failures without LLM calls, and transactionally
  enforce USD 1/job and USD 10/deployment UTC-day exposure.
- **Read when**: Changing model IDs or prompts, extraction/recovery/classification routing,
  deterministic failure short-circuiting, LLM quality escalation, token pricing, coordinator job
  scope, daily/provider cost accounting, or replay qualification.

### ADR-030: Shared progress-aware Booking.com browser recovery
- **Status**: accepted
- **Date**: 2026-08-02
- **Bolt**: 038-shared-booking-browser-recovery (shared-booking-browser-recovery)
- **Path**: `bolts/038-shared-booking-browser-recovery/adr-030-shared-progress-aware-booking-browser-recovery.md`
- **Summary**: Ref-based repetition and action-executed feedback let unchanged pages consume the
  full budget, while account inventory had no LLM seam. Use one provider-neutral recovery contract
  with structured progress evidence, semantic loop control, forced visual reorientation, step-local
  limits, all-page safety checks, and deterministic inventory-completeness authority.
- **Read when**: Modifying browser-agent observations, prompts, progress/loop control, per-step LLM
  budgets, popup handling, account-inventory recovery, LLM usage accounting, or replay evaluation.

### ADR-029: Persisted random daily scheduling
- **Status**: accepted
- **Date**: 2026-08-01
- **Bolt**: 037-randomized-daily-booking-checks (randomized-daily-booking-checks)
- **Path**: `bolts/037-randomized-daily-booking-checks/adr-029-persisted-random-daily-scheduling.md`
- **Summary**: A global fixed interval cannot provide per-user broad daily coverage or restart-safe
  jitter. Persist independently randomized UTC slots per user/date, retain the interruptible stdlib
  wait loop, and acquire the existing coordinator gate before atomically claiming due work.
- **Read when**: Changing scheduled-check timing, randomization, daily slot persistence, missed-run
  recovery, scheduler waiting, caller next-run status, or coordinator admission ordering.

### ADR-028: Gate absence reconciliation on complete inventory traversal
- **Status**: accepted
- **Date**: 2026-07-27
- **Bolt**: 034-booking-account-sync-core (booking-account-sync-core)
- **Path**: `bolts/034-booking-account-sync-core/adr-028-completeness-gated-reconciliation.md`
- **Summary**: Dynamic Booking.com inventory can be partially observed. Only recognized complete
  traversal evidence permits unseen synchronized reservations to become absent.
- **Read when**: Working on Booking.com account discovery, pagination, synchronization completeness,
  lifecycle reconciliation, stale inventory, or absence-based state changes.

### ADR-027: Booking.com account inventory is authoritative
- **Status**: accepted
- **Date**: 2026-07-27
- **Bolt**: 034-booking-account-sync-core (booking-account-sync-core)
- **Path**: `bolts/034-booking-account-sync-core/adr-027-account-inventory-authoritative-projection.md`
- **Summary**: Manual local booking truth conflicts with authenticated account evidence. Persist the
  complete synchronized account inventory and derive strict eligible monitoring projections only.
- **Read when**: Working on booking registration/edit/delete, account synchronization, booking
  persistence, eligibility, guided rebooking, or monitoring projection lifecycle.

### ADR-026: Telegram-bound HTTPS remote browser login
- **Status**: accepted
- **Date**: 2026-07-20
- **Bolt**: 026-remote-authentication-gateway (remote-authentication-gateway)
- **Path**: `bolts/026-remote-authentication-gateway/adr-026-telegram-bound-remote-browser-login.md`
- **Summary**: `/connect` uses a Telegram-signed, short-lived HTTPS Mini App to control one temporary
  VPS mobile Chromium through noVNC. Positive Booking.com authentication is captured into the encrypted
  per-user vault, and all transient resources are torn down; the trusted-VPS compromise boundary remains explicit.
- **Read when**: Working on Booking.com login/session intake, Telegram Mini Apps, inbound HTTPS,
  noVNC/websockify, remote browser isolation, reconnect prompts, or VPS credential threat models.

### ADR-025: Authenticated mobile web is the primary price context
- **Status**: accepted
- **Date**: 2026-07-19
- **Bolt**: 025-authenticated-mobile-web-monitoring (authenticated-mobile-web-monitoring)
- **Path**: `bolts/025-authenticated-mobile-web-monitoring/adr-025-authenticated-mobile-web-price-source.md`
- **Summary**: Telegram-owned checks use an allowlisted Android-like Chromium mobile profile and the
  booking owner's validated session. A price is accepted only with complete redacted provenance;
  native-app/app-only promotions remain outside Playwright's guaranteed scope.
- **Read when**: Changing browser contexts, mobile profiles, authentication/Genius evidence,
  check provenance, search extraction, or final phone handoff behavior.

### ADR-024: Encrypted per-user Booking.com sessions
- **Status**: accepted
- **Date**: 2026-07-19
- **Bolt**: 024-per-user-booking-sessions (per-user-booking-sessions)
- **Path**: `bolts/024-per-user-booking-sessions/adr-024-encrypted-per-user-booking-sessions.md`
- **Summary**: ADR-010's global JSON/base64 state is replaced by one Fernet-encrypted session bundle
  per stable local user, resolved only after ownership/access checks and restored into a clean context.
  Telegram-owned checks fail closed instead of using owner/global/public fallback.
- **Read when**: Working on cookie import, session persistence/encryption, user isolation, browser
  context lifecycle, authentication failures, or legacy session migration.

### ADR-023: Stable-ID atomic post-rebook propagation
- **Status**: superseded by ADR-027
- **Date**: 2026-07-19
- **Bolt**: 023-post-rebook-monitoring (post-rebook-monitoring)
- **Path**: `bolts/023-post-rebook-monitoring/adr-023-stable-id-post-rebook-propagation.md`
- **Summary**: A detected savings opportunity is not a checkout receipt and successful device-side
  rebooking otherwise leaves the old baseline monitored. A validated replacement updates the same
  stable booking ID in one guarded transaction, while completed cancellation archives immediately
  until a validated replacement can reactivate it.
- **Read when**: Changing rebook outcome handling, monitored booking replacement, baseline updates,
  stale-savings invalidation, or transaction rules around device-side rebooking.

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
- **Status**: superseded by ADR-027
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
- **Status**: superseded by ADR-029
- **Date**: 2026-07-01
- **Bolt**: 002-core-local-data (core-local-data)
- **Path**: `bolts/002-core-local-data/adr-006-threading-event-scheduler.md`
- **Summary**: The original fixed-interval premise is superseded by ADR-029. Its
  `threading.Event.wait(timeout)` shutdown mechanism remains in the adaptive durable scheduler.
- **Read when**: Reviewing the history of scheduler mechanics; use ADR-029 for current timing,
  persistence, jitter, retry, and shutdown decisions.

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
