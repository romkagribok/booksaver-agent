---
intent: 007-telegram-on-demand-checks
phase: construction
status: complete
created: 2026-07-18T23:40:00Z
updated: 2026-07-18T23:57:35Z
---

# Requirements: Telegram On-Demand Checks

## Intent Overview

Let an authorized Telegram user run the normal live Booking.com price check for one of their own
active bookings immediately. The command stays responsive by admitting the request synchronously and
performing the browser work in a shutdown-aware background worker. Scheduled and on-demand work share
one coordinator, one concurrency gate, the same per-user daily budgets, and the existing trace,
savings, and notification pipeline.

## Functional Requirements

### FR-1: Discover and select an immediate check

- **Description**: Publish `/checknow` in the shared command catalog. With no argument it renders the
  caller's active bookings as buttons; a typed exact ID or unique prefix of at least eight characters
  selects the same operation.
- **Acceptance Criteria**:
  - `/checknow` appears in `/start`, `/help`, and applicable native Telegram command menus.
  - The no-argument picker contains only caller-owned active bookings with recognizable labels.
  - Exact IDs and unique caller-scoped prefixes of eight or more characters are accepted.
  - Missing, ambiguous, stale, inactive, foreign, or malformed selectors disclose no foreign data.
- **Priority**: Must
- **Related Stories**: US-052

### FR-2: Run and report a real check without blocking Telegram

- **Description**: After admission, run the existing Booking.com monitor in the background and send a
  concise completion or failure result to the requesting chat.
- **Acceptance Criteria**:
  - Command and callback handling acknowledge promptly before browser navigation begins.
  - The worker re-resolves the active Telegram user, booking ownership, and booking status immediately
    before execution.
  - Success reports property, current price, currency, and check ID prefix; failure reports a concise
    code/detail and check ID prefix.
  - Shutdown prevents new work and workers observe the shared stop signal; daemon shutdown never waits
    indefinitely for an on-demand thread.
- **Priority**: Must
- **Related Stories**: US-053

### FR-3: Coordinate scheduled and on-demand execution

- **Description**: Extract the scheduled check closure into one daemon-lifetime coordinator used by
  both scheduler ticks and `/checknow`.
- **Acceptance Criteria**:
  - At most one Booking.com browser/check batch runs in the process at a time.
  - A manual request for a booking already in flight, or while another scheduled/manual batch owns the
    browser gate, receives an immediate busy response and is not queued.
  - A scheduled tick that finds the coordinator busy exits cleanly; the next interval retries normally.
  - Scheduler and Telegram code do not duplicate browser, persistence, monitor, savings, or notifier
    orchestration.
- **Priority**: Must
- **Related Stories**: US-054

### FR-4: Share and enforce daily user budgets

- **Description**: Scheduled and on-demand checks consume the same thread-safe, UTC-day counters for
  checks and LLM calls.
- **Acceptance Criteria**:
  - No scheduled plan or manual request can exceed `max_checks_per_user_per_day`, including when a
    user has more bookings than their remaining allowance.
  - Every admitted real check consumes one check allowance and persisted skipped results continue to
    use `user_check_limit_reached` where applicable.
  - Actual LLM calls are counted per booking owner across both paths.
  - A check with no remaining daily LLM allowance still runs using scripted/DOM interpretation only;
    otherwise its per-check LLM cap is reduced to the remaining daily allowance.
  - Existing once-per-day check-cap notice behavior remains best-effort and shared.
- **Priority**: Must
- **Related Stories**: US-055

### FR-5: Preserve the normal monitoring outcome pipeline

- **Description**: Immediate checks are ordinary BookSaver checks, not a separate lightweight scrape.
- **Acceptance Criteria**:
  - They use the existing session mode, search monitor, agent action guard, timeout, trace repository,
    failure tracker, check history, snapshot writer, and per-user LLM-key resolution.
  - Results pass through the existing savings pipeline and owner notifier resolver.
  - A detected saving sends the existing proactive per-user savings alert in addition to the concise
    `/checknow` completion message.
  - No autonomous reservation, purchase, or cancellation authority is added.
- **Priority**: Must
- **Related Stories**: US-056

## Non-Functional Requirements

### Security and Privacy

- Callback data and typed identifiers are untrusted selectors; ownership is checked at selection and
  again in the worker.
- Foreign/stale selections use non-disclosing responses and never start a browser.
- Existing owner/invite gateway admission and action guards remain authoritative.

### Reliability and Responsiveness

- One daemon process owns one check coordinator and never runs competing Playwright browsers.
- Telegram polling remains available throughout a live check.
- Callback payloads remain within Telegram's 64-byte UTF-8 limit and are acknowledged.
- Daily counters are thread-safe and roll over atomically at UTC midnight.

### Compatibility and Verification

- Existing scheduled-check behavior, persistence, traces, alerts, command navigation, and rebooking
  remain compatible.
- Ruff, mypy, focused coordinator/Telegram/monitor tests, full pytest, diff checks, and AI-DLC
  validators are clean.

## Constraints

- Use the existing synchronous Playwright monitor and stdlib threading; add no process, scheduler,
  runtime dependency, or schema migration.
- Retain in-memory daily-counter restart semantics documented by US-031.
- Do not create a Telegram-specific monitor or a second scheduler.
- BookSaver remains self-hosted, Booking.com-hotel-only, and confirmation-gated for rebooking.

## Assumptions and Decisions

- Busy requests are rejected immediately rather than queued. This prevents stale delayed checks,
  duplicate work, and shutdown surprises.
- The global browser gate serializes whole batches. A scheduled tick skips when busy rather than
  waiting behind an interactive request.
- Check allowance is reserved immediately before browser execution. An admitted worker that loses
  authorization before that point consumes no allowance.
- Exhausting the daily LLM budget disables LLM use for that check instead of blocking DOM/scripted
  monitoring; actual browser checks remain useful without an LLM when the page follows known seams.
- The product owner's request authorizes continuous Inception and Construction progression through
  the final Test checkpoint; closure, commit, merge, and push remain separately gated.

## Scope Exclusions

- Queued checks, cancellation of an in-flight browser check, progress streaming, or bulk “check all.”
- Persisting daily counters across daemon restarts.
- Running more than one browser concurrently or distributing work across processes/hosts.
- Changing Booking.com reservations or relaxing guided-rebook confirmation.
