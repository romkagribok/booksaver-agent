---
intent: 002-agentic-search-monitor
phase: inception
status: complete
created: 2026-07-05T22:53:18Z
updated: 2026-07-05T23:05:00Z
---

# Requirements: Agentic Search Monitor

## Intent Overview

Replace the MVP's manage-page price check with a **search-based price discovery flow**. The MVP
(intent 001) opens `myreservations.html` and parses a "live price" from it — but Booking.com never
re-quotes an existing reservation there, so that check cannot surface real savings. Real savings
appear only when the same property and dates are **searched again as a new customer** and a cheaper
equivalent refundable offer is found, which the user can then cancel-and-rebook into.

This intent adds a **hybrid agentic browser flow**: deterministic Playwright drives the known steps
of the full search journey (search box → results → property page → room table), and an **LLM browser
agent** takes over when the scripted path fails or a page needs judgment (layout changes, popups,
room-table interpretation, refundability wording). The discovered *bookable total* for an equivalent
room feeds the **existing** savings-detection → notification → guided-rebook pipeline unchanged.

**Type**: Enhancement (brown-field) — replaces the price-source component inside unit
`002-booking-com-price-monitor`'s runtime slot; everything downstream (savings, notifications,
rebook) is preserved.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Find real, actionable savings | A price check produces a bookable total from a live search for an equivalent refundable room, not a parsed reservation figure | Must |
| Survive Booking.com UI drift | When a scripted step fails, the LLM agent completes the step or the check fails with a diagnosable reason — never a silent wrong price | Must |
| Keep daemon cost bounded | Hard, configurable caps on agent steps and LLM calls per check; exceeding a cap is a recorded failure, not a runaway loop | Must |
| Preserve MVP safety posture | No autonomous cancel/purchase; search flow is strictly read-only on the account | Must |

---

## Functional Requirements

### FR-1: Full search journey with saved session
- **Description**: On each scheduled check, the monitor performs the complete user search journey on
  Booking.com using the saved authenticated session (`booksaver auth`): open booking.com, enter the
  property/destination query derived from the registered booking (property name), set the exact
  check-in/check-out dates and occupancy, submit the search, locate the registered property in the
  results, open its property page, and read the room/rate table. No deep-link shortcut is used — the
  flow sees exactly the prices a real returning customer would see (including member/Genius rates
  tied to the session).
- **Occupancy**: the search must use the booking's real occupancy, never a silent default. `Booking`
  gains a required `Occupancy` value object (adults ≥ 1, children ≥ 0, rooms ≥ 1) captured at
  registration; existing bookings are migrated to an "occupancy missing" state and their checks fail
  with a clear message until the user sets occupancy via CLI.
- **Acceptance Criteria**:
  - Given an active booking, a check navigates search → results → property page → room table without
    manual input.
  - The property opened is verified to be the registered property (name/ref match), not a look-alike
    from the results list.
  - Dates and occupancy on the property page match the registered `StayDates` before any price is read.
  - The session cookies are restored before the journey and refreshed cookies persisted after, as in MVP.
- **Priority**: Must
- **Related Stories**: US-017, US-018

### FR-2: Equivalent-offer extraction (bookable total)
- **Description**: From the property page's room table, the system identifies candidate offers
  equivalent to the registered booking — same property, same dates, same room type, still refundable —
  and extracts each candidate's **all-in bookable total** (the total a user would pay, including
  taxes/charges as displayed at booking time) plus its refundability wording. The cheapest equivalent
  refundable candidate becomes the check's live price.
- **Acceptance Criteria**:
  - Extraction returns room label, all-in total (amount + currency), and refundability evidence
    (raw cancellation-policy text) per candidate.
  - Room-type matching handles naming drift (e.g. "Double Room" vs "Standard Double Room") via LLM
    judgment with a stated confidence; below-threshold matches are excluded, never guessed into savings.
  - Non-refundable rates and rates for different occupancy/dates are excluded.
  - The selected candidate is emitted as a `CheckResult` compatible with the existing savings pipeline
    (same success shape as MVP: live price + refund indicators + extraction method).
- **Priority**: Must
- **Related Stories**: US-019

### FR-3: Hybrid agent escalation
- **Description**: The journey is scripted-first: deterministic Playwright with stable selectors and
  explicit waits executes each step. When a step fails (selector missing, unexpected page, popup/
  overlay, consent wall, ambiguous room table), an LLM browser agent is invoked with a snapshot of the
  current page state and a bounded action vocabulary (click, fill, select, scroll, extract, give-up)
  to complete **that step**, then control returns to the script. The LLM is an actor when needed, not
  merely a text parser. **Observations are tiered**: the agent first receives a distilled text/DOM
  snapshot (visible text + interactive elements with stable references); a Playwright screenshot is
  attached for vision only when the text observation is insufficient (agent signals it cannot orient,
  or two consecutive actions fail). Screenshot turns count double against the step cap.
- **Acceptance Criteria**:
  - Every scripted step has a defined escalation point; escalations are logged with step name and reason.
  - The agent acts only through the sanctioned action vocabulary; no arbitrary JS execution against the page.
  - Agent actions never navigate into cancel/booking/payment flows — a URL/action guard blocks
    reservation-mutating targets (cancellation pages, checkout/"book now" submission).
  - A check where the agent gives up records a failure with the step and the agent's stated reason.
- **Priority**: Must
- **Related Stories**: US-018, US-020

### FR-4: Hard cost caps per check
- **Description**: Config-driven hard caps bound each check: max LLM agent steps, max total LLM calls
  (agent + extraction), and a wall-clock timeout per booking check. Exceeding any cap aborts the check
  with a distinct failure code. *Documented note: caps are the deliberately simple MVP of cost control —
  smarter adaptive budgeting (e.g. per-day budgets, backoff on repeated escalation) is future work if
  hard caps prove too blunt.*
- **Acceptance Criteria**:
  - Caps configurable in `config.toml` with safe defaults (proposed: 15 agent steps, 20 LLM calls,
    180 s per check); validated at config load.
  - Cap breach → `CheckResult` failure with a specific failure code (e.g. `BUDGET_EXCEEDED`), visible
    in check history and logs.
  - The daemon proceeds to the next booking/next cycle normally after a cap breach.
- **Priority**: Must
- **Related Stories**: US-021

### FR-5: Search flow replaces manage-page price source
- **Description**: The search flow becomes the **sole producer** of live prices. The manage page is no
  longer used for price extraction; session validation (is-authenticated checks) is retained. Existing
  savings detection, equivalence gate, notifications, and guided rebook consume the new results unchanged.
- **Acceptance Criteria**:
  - `BookingComMonitor.run_check` (or its replacement) no longer opens `myreservations.html` for prices.
  - Savings pipeline, notifiers, and rebook flow require no interface changes; existing tests for those
    units still pass.
  - Check history records the extraction method distinguishing scripted vs agent-assisted checks.
- **Priority**: Must
- **Related Stories**: US-019, US-022

### FR-6: Diagnosability of agent runs
- **Description**: Each check produces a local, inspectable trace: ordered step log (scripted and agent
  steps, actions taken, escalation reasons), and on failure a page snapshot (HTML text and/or screenshot)
  stored under the data directory with rotation.
- **Acceptance Criteria**:
  - `booksaver` CLI can show the step trace for a given check (new subcommand or extension of existing).
  - Failure snapshots are written locally, capped in count/size, and never leave the machine.
  - Traces redact credentials/cookies.
- **Priority**: Should
- **Related Stories**: US-022

---

## Non-Functional Requirements

### Performance
| Requirement | Metric | Target |
|-------------|--------|--------|
| Check duration | Wall-clock per booking check | ≤ 180 s hard timeout (configurable) |
| Scheduler impact | A slow/failed check must not delay other bookings beyond its own timeout | Sequential checks proceed after timeout |

### Cost
| Requirement | Metric | Target |
|-------------|--------|--------|
| LLM usage per check | LLM calls (agent + extraction) | ≤ 20 hard cap (configurable); happy path scripted-only uses ≤ 2 (room-match + refundability judgment) |
| Agent loop bound | Agent steps per check | ≤ 15 hard cap (configurable) |

### Reliability
| Requirement | Metric | Target |
|-------------|--------|--------|
| No silent wrong prices | Confidence gating | Below-threshold extraction/match → failure, never a savings signal |
| Failure isolation | Daemon uptime | Any check failure (cap, agent give-up, navigation) is recorded and the daemon continues |

### Security / Safety
| Requirement | Standard | Notes |
|-------------|----------|-------|
| Read-only account actions | Action guard | Agent may never trigger cancellation, checkout, or payment; guarded by URL/action denylist at the adapter level |
| Local-only | MVP constraint | Page snapshots, traces, session data stay on the user's machine; LLM API calls carry page content only (no cookies/credentials) |
| Secrets | ADR-002 | Unchanged — env vars only |

---

## Constraints

### Technical Constraints

**Project-wide standards**: loaded from `memory-bank/standards/` by the Construction Agent.

**Intent-specific constraints**:
- Hexagonal layout preserved: search-journey orchestration is application/monitor-layer logic; Playwright
  stays behind the browser port; the LLM agent goes behind a new driver/agent port next to `LLMExtractor`.
- Runtime deps remain **playwright + anthropic** only (ADR-003/007/009); the agent loop is built on the
  anthropic SDK directly, no agent frameworks.
- Existing domain vocabulary reused: `CheckResult`, `Money`, `StayDates`, `RoomType`, equivalence rules
  from `003-savings-detection-notifications`.
- Full search journey only (user decision) — no property-page deep-linking, even as a fallback.

### Business Constraints
- Booking.com hotels only; refundable bookings only (unchanged product constraints).
- No autonomous cancel or purchase — this intent is strictly price discovery.

---

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| Property name + dates as search query reliably surfaces the registered property in results | Wrong/missing property → checks fail | LLM agent disambiguates results; property identity verified before reading prices; failure recorded if unverifiable |
| Saved session survives the search journey (no captcha/bot wall on most checks) | Frequent AUTH_REQUIRED/blocked checks | Reuse MVP reauth flow; record distinct failure code for bot-detection walls; back off via existing failure tracker |
| All-in total is visible on the property page room table for the session's currency | Totals mislead (excluded taxes) | Extraction targets the displayed total incl. charges wording; currency mismatch with baseline → excluded from savings (existing rule) |
| Hard caps are acceptable UX for MVP of this intent | Checks fail often on cap | Documented as deliberate simplification; adaptive budgeting is named future work |

---

## Open Questions

| Question | Owner | Due Date | Resolution |
|----------|-------|----------|------------|
| Screenshot-based vs text/DOM-snapshot-based agent observations | User | 2026-07-05 | **Resolved**: tiered — text/DOM snapshot first, screenshot escalation only when text is insufficient (FR-3) |
| Occupancy source — default vs registration field | User | 2026-07-05 | **Resolved**: required `Occupancy` field at registration + migration path for existing bookings; no silent default (FR-1) |
