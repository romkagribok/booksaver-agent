---
intent: 010-telegram-privacy-boundaries
phase: inception
status: complete
created: 2026-07-19T02:29:55Z
updated: 2026-07-19T14:48:51Z
---

# Requirements: Telegram Privacy Boundaries

## Intent Overview

Make user-data isolation explicit across every Telegram interaction. Commands, callbacks, dialogs,
background completions, and proactive messages operate only in private chats and expose exact booking,
check, savings, rebook, and result data only to the owning active user. The owner/admin may see
identity and aggregate usage needed to operate the bot, but no other user's exact records through the
Telegram interface.

This guarantee applies to Telegram, not to the owner of the self-hosted VPS: a machine administrator
can inherently read local SQLite, traces, snapshots, and logs. Hiding data from the host owner would
require a different client-side encryption architecture and is outside this intent.

It is bot-user isolation in Telegram's interface, not end-to-end secrecy from Telegram, Booking.com,
the configured LLM provider, or the host operator; existing product flows send required data to those
processors under their established boundaries.

## Functional Requirements

### FR-1: Restrict interaction to private Telegram chats

- **Description**: Commands, callbacks, dialogs, key intake, and replies containing user data must be
  accepted only when Telegram reports a private chat.
- **Acceptance Criteria**:
  - Message and callback envelopes carry the server-provided Telegram chat type into the access
    boundary.
  - Missing or unknown chat types fail closed as non-private.
  - Group, supergroup, and channel commands/callbacks receive a generic refusal and trigger no
    database mutation, dialog transition, key validation, browser/LLM work, or private-data response.
  - Plain-text dialog replies and pasted key material in a non-private chat are ignored/refused before
    dialog/key handlers run.
  - Authorization by an active sender ID cannot override the private-chat requirement.
  - Private-chat behavior remains unchanged for admitted users.
- **Priority**: Must
- **Related Stories**: US-067

### FR-2: Scope status and exact-data selectors to the caller

- **Description**: `/status` and every exact-data command, callback, registration, and edit must query
  only the current active user's ownership scope and use non-disclosing conflict responses.
- **Acceptance Criteria**:
  - `/status` may show uptime, next run, and session mode plus caller-only aggregate counts; it never
    enumerates any property, booking/check ID, outcome, failure, or another user's count.
  - `/bookings`, `/checks`, `/savings`, `/checknow`, `/editbooking`, `/deletebooking`, `/rebook`, and
    their callbacks continue to resolve only caller-owned records.
  - Foreign exact IDs/prefixes/callback payloads behave identically to missing/stale records and
    perform no mutation, LLM call, browser work, or completion disclosure.
  - Registration and confirmation-ID edits preserve global uniqueness without confirming that a
    guessed confirmation belongs to another user; foreign conflict and generic invalid/conflict
    responses are indistinguishable.
  - The owner sees exact data only for the owner's own records through ordinary commands; owner role
    does not bypass ownership.
- **Priority**: Must
- **Related Stories**: US-068

### FR-3: Restrict owner administration to aggregate usage

- **Description**: `/admin users`, revoke/purge pickers, and future admin summaries use an explicit
  aggregate allowlist and never load another user's exact domain records into Telegram formatting.
- **Acceptance Criteria**:
  - Admin user rows show `@username` or an internal fallback, access state, active-booking count, checks
    today, and LLM calls today. Owner/user role may be shown where operationally necessary.
  - In-memory daily values are labeled `today (resets at UTC midnight and daemon restart)`; checks are
    reserved/executed attempts and LLM calls are actual metered calls.
  - Output omits chat IDs, personal-key state, properties/references, confirmations, dates, rooms,
    booking/check/opportunity IDs, prices/currencies, outcomes/failures, savings, cancellation data,
    traces/snapshots, and rebook events.
  - Revoke/purge callbacks carry only an internal user identifier and display no exact owned data.
  - Aggregate usage is exposed through a dedicated projection/query and cannot be used to select exact
    records. A narrow injected usage provider merges SQL `COUNT` aggregates with CheckCoordinator
    counter snapshots; if runtime counters are unavailable the output says usage is unavailable
    rather than fabricating zeros.
- **Priority**: Must
- **Related Stories**: US-069

### FR-4: Make revocation immediate across asynchronous work and messages

- **Description**: Revoking a user must prevent queued or later stages of scheduled checks, immediate
  checks, guided rebooking, cap/key notices, and alerts from running or disclosing data.
- **Acceptance Criteria**:
  - Scheduled plans reauthorize the active user immediately before allowance reservation and browser
    work; queued bookings for a newly revoked user are skipped without a persisted cap result.
  - `/checknow` reauthorizes before work and completion; browser work already running may finish and
    persist locally when safe cancellation is impractical, but a revoke suppresses SavingsPipeline,
    key/cap notices, sensitive completion details, and alerts.
  - Rebook workers reauthorize user and opportunity ownership at worker start and before each prompt,
    confirmation, handoff link, and final reply. Confirmation waits poll an active-user predicate or
    receive a revocation signal so loss of access terminates within a bounded interval and releases
    the active-session guard rather than waiting for the full confirmation timeout.
  - Check-cap and invalid-personal-key notices require the target user to remain active.
  - Savings alerts continue to resolve only an active booking owner and never fall back across users.
  - No browser/LLM work begins for queued work whose user has become revoked.
- **Priority**: Must
- **Related Stories**: US-070

### FR-5: Prove isolation by construction and adversarial regression

- **Description**: Telegram adapters use caller-scoped query/service boundaries for exact data and a
  distinct admin aggregate projection, backed by a centralized two-user privacy regression matrix.
- **Acceptance Criteria**:
  - A privacy matrix identifies every command, callback/dialog family, asynchronous completion, and
    proactive notification with its data class, authorization seam, and denial behavior.
  - Tests seed two users with unique sentinel properties, confirmations, booking/check/opportunity IDs,
    prices, outcomes, failure details, and savings, then assert neither user's responses contain the
    other's sentinels.
  - Crafted foreign callbacks cover `checks:`, `checknow:`, `bedit:`, `bdel:`, and `rebook:select:`;
    typed flows cover all corresponding commands plus registration/edit confirmation conflicts.
  - Group/supergroup message, callback, dialog, and key-intake tests prove zero state/LLM/browser work.
  - Revocation race tests cover scheduled-plan delay, immediate-check execution, rebook prompts, cap
    notices, invalid-key notices, and savings routing.
  - Admin projection tests seed exact-data sentinels and fail if formatting invokes any exact booking,
    check, savings, trace, or rebook repository method; only aggregate SQL and counter snapshots are
    permitted.
  - Existing owned-user behavior remains functional and full pytest, Ruff, mypy, diff, and AI-DLC
    gates pass.
- **Priority**: Must
- **Related Stories**: US-071

## Non-Functional Requirements

### Privacy and Security

- Least privilege applies equally to owner and invited users for exact booking-derived data.
- Administrative authorization and record ownership are independent: owner status grants user
  administration, not another user's record access.
- Unknown, foreign, stale, ambiguous, and unauthorized selectors remain non-enumerating.
- Access logs contain sender ID and command/action family only; invite codes, usernames, properties,
  URLs, prices, and message bodies are excluded.

### Reliability and Compatibility

- Existing owned-user registration, editing/deletion, scheduled checks, `/checknow`, notifications,
  and guided rebooking remain functional.
- Privacy-specific changes require no schema migration; username storage belongs to Intent 009's v9
  migration.
- Privacy denial happens before any expensive or mutating operation.

### Verification

- Focused two-user Telegram/persistence/coordinator/notifier/rebook tests plus full Ruff, mypy, pytest,
  diff, and AI-DLC validation must pass.

## Constraints

- Keep the self-hosted single-process architecture, current SQLite ownership relation, and stdlib
  Telegram client.
- Do not expose local CLI trace/admin capabilities over Telegram.
- Do not add a web dashboard, analytics service, telemetry backend, or host-versus-user encryption
  model.

## Assumptions and Decisions

- "Admin sees only usage" is a Telegram UI guarantee, not protection from the root/operator of the
  self-hosted host.
- The owner can inspect the owner's own exact records through ordinary caller-scoped commands.
- Aggregate usage is limited to identity/access plus counts; personal-key state and exact outcomes are
  excluded.
- This is a separate intent because it establishes a cross-cutting authorization/privacy policy rather
  than invite presentation.
- The product owner authorized continuous Inception and Construction through final Test, then
  approved the combined final review and closure.

## Scope Exclusions

- Encrypting the complete database against the VPS owner, multi-owner roles, delegated support access,
  downloadable reports, or external analytics.
