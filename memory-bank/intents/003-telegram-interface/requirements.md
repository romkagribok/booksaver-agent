---
intent: 003-telegram-interface
phase: inception
status: draft-pending-validation
created: 2026-07-10T02:15:00Z
updated: 2026-07-10T02:15:00Z
---

# Requirements: Telegram as the Main Interface

## Intent Overview

Make a **Telegram bot the primary user interface** for BookSaver. Today every interaction
(registration, occupancy backfill, savings review, rebook confirmation) happens through the local CLI,
and Telegram is a one-way alert channel. This intent inverts that: the daemon runs unattended on a
**VPS**, and users do everything through a conversation with the bot — register bookings by answering
the bot's questions, receive savings alerts, inspect check status, and confirm rebook steps.

Because the bot may be **discoverable** (anyone can find and message it), access is gated: users who
are not on the owner's allowlist must **bring their own Anthropic API key** before the bot does any
LLM-consuming work for them. Each user's checks are billed against their own key; the owner pays only
for the VPS compute.

**Type**: Enhancement + deliberate scope amendment (brown-field). This intent **amends the "local-only,
single-user" MVP constraint**: the daemon becomes a small self-hosted multi-user service. It remains
self-hosted (no BookSaver cloud backend, no third-party data sharing) — "local" now means "on the
owner's VPS" instead of "on the user's laptop". Requires a new ADR superseding the local-only wording
of US-013 for this deployment mode (the laptop mode keeps working).

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Zero-CLI onboarding | A new user can go from `/start` to a registered, monitored booking entirely in Telegram chat | Must |
| Safe sharing | A stranger who discovers the bot cannot consume the owner's LLM budget or see anyone else's data | Must |
| Unattended operation | Daemon + bot run on a VPS with no attached display; checks and alerts continue for days without operator action | Must |
| Rebook stays human-gated | Rebook confirmations move to Telegram but keep the mandatory explicit-confirmation state machine; final booking click always happens on the user's own device | Must |

---

## Functional Requirements

### FR-1: Telegram bot gateway inside the daemon
- **Description**: The daemon gains a Telegram **update loop** (long polling via `getUpdates`,
  stdlib urllib per ADR-011 — no bot framework) running as a thread beside the scheduler in the same
  single process. A command router dispatches `/start`, `/help`, `/status`, `/bookings`, `/savings`,
  `/checks`, `/register`, `/setkey`, `/rebook`, `/cancelflow`. A per-chat **conversation state
  machine** supports multi-step dialogs (registration, key intake, rebook confirmation).
- **Acceptance Criteria**:
  - Bot answers commands while scheduled checks run; a slow check never blocks bot responses.
  - Unknown input inside a dialog re-prompts with the expected format; `/cancelflow` aborts any dialog.
  - Bot restarts cleanly with the daemon; no updates are double-processed after restart (offset persisted).
- **Priority**: Must
- **Related Stories**: US-023, US-024

### FR-2: Access control for a discoverable bot
- **Description**: Every incoming update is resolved to a user identity (Telegram user ID). Config
  defines an access mode: `owner` (only listed chat IDs), `invite` (allowlist grows via owner-issued
  invite codes), or `open` (anyone may start, but all LLM-consuming features are locked until the user
  provides their own Anthropic API key — FR-3). Unauthorized users get a clear refusal message and are
  rate-limited.
- **Acceptance Criteria**:
  - In `owner` mode, non-listed users cannot trigger any stateful action or LLM call.
  - In `open` mode, `/register` and checks are refused until a valid key is stored for that user.
  - Owner has admin commands to list/revoke users.
- **Priority**: Must
- **Related Stories**: US-026, US-028

### FR-3: Bring-your-own Anthropic API key
- **Description**: The bot asks non-owner users for their Anthropic API key in chat (`/setkey` or
  prompted during onboarding). The key is validated with a minimal live call, stored **encrypted at
  rest** on the VPS, and used for *all* LLM work on that user's bookings (extraction + browser agent).
  The message containing the key is deleted from the chat where the Bot API allows it, and the key is
  never echoed, logged, or included in traces.
- **Acceptance Criteria**:
  - Invalid/revoked keys produce an immediate, actionable error; checks for that user fail with a
    distinct failure code (`USER_KEY_INVALID`) until fixed.
  - Keys are redacted in logs, traces, and snapshots (reuse trace-redaction seam from intent 002).
  - User can rotate (`/setkey` again) and delete (`/deletekey`) their key; deletion pauses their checks.
- **Priority**: Must
- **Related Stories**: US-027, US-028

### FR-4: Conversational booking registration
- **Description**: `/register` starts a guided dialog collecting everything monitoring + rebook need:
  property name (and optionally Booking.com property URL), check-in/check-out dates, room type,
  baseline all-in price + currency, refundability confirmation, occupancy (adults/children/rooms), and
  confirmation ID. The bot validates each answer with the **same domain rules as the CLI** (refundable
  only, hotels only, occupancy ≥ 1 adult, future dates) and replays a summary for a final yes/no before
  saving. Existing CLI registration keeps working for laptop mode.
- **Acceptance Criteria**:
  - A completed dialog produces the same `Booking` aggregate as CLI registration (one shared
    application-layer path).
  - Non-refundable or non-hotel answers are rejected mid-dialog with the same product-constraint
    messages as the CLI.
  - `/bookings` lists the user's own bookings only.
- **Priority**: Must
- **Related Stories**: US-025

### FR-5: Multi-user data scoping and notification routing
- **Description**: Persistence gains a `users` table (telegram user ID, access state, encrypted key
  reference, created-at) and a `user_id` foreign key on bookings; checks, savings, rebook sessions, and
  traces inherit scope through their booking. Savings alerts route to the owning user's chat. The
  scheduler iterates all active users' bookings, resolving the correct LLM client per booking.
- **Acceptance Criteria**:
  - Schema migration (v7) assigns all existing rows to the owner user; laptop single-user mode is the
    degenerate case (one user) with no behavior change.
  - No query path can return another user's bookings/savings/checks (enforced in repository layer).
  - A savings alert goes only to the booking owner's chat.
- **Priority**: Must
- **Related Stories**: US-029, US-030

### FR-6: Per-user cost caps and abuse limits
- **Description**: Existing hard caps (ADR-017) become per-booking-check as today, plus per-user
  daily ceilings (max checks/day, max LLM calls/day) and bot-level rate limits (messages/minute per
  chat). Since users pay their own LLM bill, per-user LLM ceilings default generous but protect the
  VPS from browser-time abuse (Playwright compute is owner-paid).
- **Acceptance Criteria**:
  - Config validates per-user limits; breaches produce polite bot messages, not silence.
  - One abusive user cannot starve other users' scheduled checks (fair scheduling per user).
- **Priority**: Must
- **Related Stories**: US-031

### FR-7: Rebook confirmation over Telegram + device handoff
- **Description**: The guided-rebook confirmation state machine (intent 001 unit 004) gets a Telegram
  `ConfirmationGate` adapter: each mandatory confirmation is an inline-keyboard yes/no in the user's
  chat, recorded in the audit trail with the Telegram message IDs. Because the browser lives on the
  VPS, the **final booking click never happens on the VPS**: after confirmation, the bot sends the user
  a deep link (property page with their dates/occupancy pre-filled) to complete the booking on their
  own device, then asks them to confirm completion so the outcome is logged.
- **Acceptance Criteria**:
  - No cancel/purchase action executes without an explicit inline-button confirmation (state machine
    unchanged, only the gate adapter differs).
  - Audit trail records channel=telegram, chat ID, message ID, timestamp per confirmation.
  - Deep link reproduces property + dates + occupancy of the savings opportunity.
- **Priority**: Must
- **Related Stories**: US-032, US-033

### FR-8: VPS deployment and headless session strategy
- **Description**: Ship a supported deployment: Dockerfile (Playwright + Chromium headless) and/or
  systemd unit, an ops runbook under `memory-bank/operations/`, and health visibility via `/status`.
  Since headed `booksaver auth` is impossible on a display-less VPS, checks default to **logged-out
  public prices** (search journey works unauthenticated); optionally a user/owner can import session
  cookies exported from their own browser to see member (Genius) rates.
- **Acceptance Criteria**:
  - One documented command path brings the daemon+bot up on a fresh VPS.
  - Checks succeed logged-out; `AUTH_REQUIRED`-class failures cannot occur in logged-out mode.
  - `/status` reports daemon uptime, last check per booking, and next scheduled run.
- **Priority**: Must (deployment), Should (cookie import)
- **Related Stories**: US-034, US-035, US-036

---

## Non-Functional Requirements

### Performance
| Requirement | Metric | Target |
|-------------|--------|--------|
| Bot responsiveness | Command reply latency while checks run | ≤ 3 s for non-LLM commands |
| Polling overhead | Telegram long-poll cycle | 25–50 s poll timeout, immediate dispatch |

### Security
| Requirement | Standard | Notes |
|-------------|----------|-------|
| User API keys | Encrypted at rest | Encryption key held in env var on VPS (`BOOKSAVER_SECRET_KEY`); never in git/DB plaintext |
| Key hygiene | Redaction | Keys never in logs, traces, snapshots, or bot replies; original key message deleted where possible |
| Data isolation | Repository-level scoping | Cross-user reads impossible by construction |
| Transport | Telegram Bot API over HTTPS | certifi CA bundle (existing fix) |

### Reliability
| Requirement | Metric | Target |
|-------------|--------|--------|
| Unattended uptime | Daemon+bot on VPS | Auto-restart on crash (systemd/Docker restart policy) |
| Update durability | Telegram offset | Persisted; no lost or duplicated commands across restarts |

---

## Constraints

### Technical Constraints
- Stdlib-first preserved: Telegram long polling via urllib (extends ADR-011); **no** python-telegram-bot
  or aiogram. Async not introduced — the update loop is a thread, matching the sync Playwright choice
  (ADR-008).
- Possible new runtime dep for encryption at rest (`cryptography`) — decision point, see Open Questions.
- Hexagonal layout: bot gateway is an inbound adapter; conversation flows call the same application
  services as the CLI; no domain logic in the bot layer.
- Single process retained: scheduler thread + bot thread in one daemon.

### Business Constraints
- Booking.com hotels only; refundable only; pragmatic equivalence — all unchanged.
- No autonomous cancel or purchase — confirmation gate moves to Telegram but stays mandatory; final
  booking click happens on the user's device, never on the VPS.
- No BookSaver-hosted backend: the VPS is owner-operated; nothing phones home anywhere else.

---

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| Booking.com search journey yields usable public prices logged-out | Logged-out prices hide member deals or journey breaks | Cookie-import option (US-035); prices are still real bookable totals either way |
| Booking.com tolerates checks from a datacenter IP | Captcha/bot walls on VPS far more often than on residential IP | Distinct failure codes already exist; document residential-proxy or home-server fallback in runbook; low check frequency |
| Telegram user ID is a sufficient identity | Impersonation via forwarded messages | IDs come from update metadata (unforgeable via Bot API), not message content |
| Users will paste an API key into a Telegram chat | Users refuse; onboarding stalls | Document scoped-key guidance (Anthropic workspace keys with spend limits); owner-mode remains keyless for allowlisted users |

---

## Open Questions (to resolve with user before construction)

| # | Question | Options | Proposed default |
|---|----------|---------|------------------|
| 1 | Scope-amendment ADR: is "self-hosted VPS, multi-user" an accepted evolution of the local-only constraint? | amend / keep laptop-only | Amend (ADR-018) |
| 2 | Key encryption at rest | `cryptography` (Fernet) dep vs stdlib-only obfuscation vs plaintext file `0600` | Fernet + `BOOKSAVER_SECRET_KEY` env var |
| 3 | Session strategy on VPS | logged-out public prices / cookie import / VNC headed login | Logged-out default, cookie import as Should |
| 4 | Telegram transport | long polling / webhook (needs public HTTPS + domain) | Long polling |
| 5 | Access mode default at first deploy | owner / invite / open | `owner`, flip to `open` when ready to share |
| 6 | Who may register how many bookings | unlimited / per-user cap | Per-user cap (default 3) |
