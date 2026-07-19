---
intent: 008-currency-aligned-price-checks
phase: inception
status: complete
created: 2026-07-19T00:28:15.000Z
updated: 2026-07-19T00:44:22.000Z
---

# Requirements: Currency-Aligned Price Checks

## Intent Overview

Ensure every live Booking.com offer is quoted and verified in the registered booking's original
baseline currency before BookSaver compares prices. The monitor must attempt a bounded currency
alignment when Booking.com localizes prices for the VPS, preserve the existing fail-closed
same-currency savings invariant, and explain unresolved mismatches clearly in traces and Telegram.

**Type**: Defect fix / reliability enhancement (brown-field).

## Scope

### In scope

- Carry the baseline currency as trusted context through search-results and property URLs.
- Verify the currencies Booking.com actually renders instead of trusting request parameters.
- Retry currency alignment once when an otherwise-equivalent refundable offer is quoted in a
  different currency.
- Preserve strict same-currency savings decisions and expose actionable mismatch diagnostics.
- Cover deterministic navigation, LLM-assisted extraction, scheduled checks, and `/checknow`.

### Out of scope

- Foreign-exchange conversion for savings decisions.
- Relabeling or automatically converting the stored baseline price.
- Relaxing property, stay, occupancy, room-equivalence, refundability, or price-total checks.
- Adding a third-party foreign-exchange-rate service.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Recover valid VPS checks localized into another currency | An otherwise-equivalent refundable offer can be re-quoted and selected in the booking's baseline currency | Must |
| Preserve trustworthy savings alerts | Zero savings opportunities compare unlike currencies or depend on an FX conversion | Must |
| Make unresolved currency behavior diagnosable | Check traces and Telegram identify requested and observed currencies without requiring source-code inspection | Must |

## Functional Requirements

### FR-1: Carry baseline currency as trusted search context

- **Description**: Every Booking.com search-results and property-page navigation must request the
  registered booking's `baseline_price.currency`. Currency joins dates and occupancy as persisted,
  trusted context; opaque result-card parameters and stale property references cannot override it.
- **Acceptance Criteria**:
  - The generated search-results URL requests the booking's three-letter baseline currency.
  - The final property URL requests that same currency while preserving the exact dates and occupancy.
  - A conflicting currency parameter in a result-card link is removed or replaced by the trusted
    baseline currency.
  - Existing property-host validation and read-only navigation guards remain unchanged.
- **Priority**: Must
- **Related Stories**: US-057

### FR-2: Verify rendered offer currency

- **Description**: BookSaver must treat the currencies parsed from rendered equivalent-offer
  candidates as truth. Requesting a currency through a URL, cookie, or visible selector is not proof
  that Booking.com honored it.
- **Acceptance Criteria**:
  - Offer candidates continue to carry explicit ISO-4217 currency codes.
  - A candidate is eligible for normal selection only when its rendered currency equals the baseline
    currency, after property, room, confidence, and refundability checks pass.
  - The monitor can distinguish an otherwise-eligible refundable candidate rejected only because of
    currency from candidates rejected for room or refundability reasons.
  - Currency symbols are never relabeled without evidence of the rendered currency.
- **Priority**: Must
- **Related Stories**: US-058

### FR-3: Perform one bounded currency-alignment recovery

- **Description**: When at least one candidate is otherwise equivalent and positively refundable but
  is rendered in a different currency, the monitor must make one bounded recovery attempt. It first
  applies Booking.com's same-site currency preference deterministically and reloads trusted booking
  context. If deterministic controls cannot complete or verify the alignment, the existing guarded
  browser agent may operate the visible currency selector within the same action, LLM-call, and
  wall-clock budgets. The room offers are then re-extracted once.
- **Acceptance Criteria**:
  - Recovery starts only when an otherwise-eligible candidate is excluded for currency mismatch.
  - At most one recovery cycle occurs per check; it cannot recurse or reset existing cost budgets.
  - Recovery preserves property, dates, occupancy, and read-only action restrictions.
  - A deterministic alignment success does not require an LLM call.
  - LLM assistance, when needed, uses the existing guarded browser action vocabulary and is recorded
    as agent-assisted work.
  - Re-extracted same-currency candidates return to the existing selection and savings pipeline.
- **Priority**: Must
- **Related Stories**: US-059

### FR-4: Fail closed with actionable currency diagnostics

- **Description**: If the recovery still cannot produce an equivalent refundable offer in the
  baseline currency, the check must not compare amounts or emit a savings opportunity. The outcome
  must be distinguishable from ordinary room/refundability mismatch.
- **Acceptance Criteria**:
  - The final failure uses a currency-specific failure code or an equally stable machine-readable
    classification rather than generic `no_equivalent_offer`.
  - Failure detail identifies the baseline currency, observed mismatched currencies, and the bounded
    recovery outcome; observed candidate totals may be included for diagnosis.
  - `/checknow` sends the user an actionable final Telegram result for this failure.
  - Scheduled checks persist the same check history and trace evidence.
  - No savings opportunity or proactive savings notification is produced for the unresolved mismatch.
- **Priority**: Must
- **Related Stories**: US-060

### FR-5: Preserve all existing check entry points and safety gates

- **Description**: Currency alignment must behave identically for scheduled checks and Telegram
  `/checknow`, without bypassing the current coordinator, quota, browser-concurrency, offer-equivalence,
  savings, notification, or guided-rebook boundaries.
- **Acceptance Criteria**:
  - Both scheduled and on-demand checks use the same currency-aligned monitor path.
  - Existing daily quotas, one-browser gate, LLM budgets, timeout, cancellation/refundability gates,
    and human-confirmed rebook flow remain effective.
  - A same-currency check that needs no recovery retains the zero-extra-LLM happy path.
  - Existing successful, no-availability, non-refundable, and room-mismatch outcomes remain compatible.
- **Priority**: Must
- **Related Stories**: US-061

## Non-Functional Requirements

### NFR-1: Safety

- Cross-currency arithmetic must never create a savings opportunity.
- No exchange-rate API, automatic FX conversion, or baseline relabeling is permitted.
- Currency recovery remains read-only and cannot approach reserve, checkout, payment, or cancellation.

### NFR-2: Boundedness

- Currency recovery adds no more than one re-navigation/re-extraction cycle per check.
- Recovery consumes the existing per-check LLM-call, agent-step, and wall-clock budgets.
- Timeout or budget exhaustion terminates with the existing bounded failure behavior.

### NFR-3: Observability

- Traces record requested currency, observed candidate currencies, whether recovery started, the
  deterministic/agent-assisted method used, and the terminal result.
- User-facing failures remain concise enough for Telegram while retaining the check ID prefix.

### NFR-4: Compatibility

- No database migration or new runtime dependency is introduced.
- Existing public/logged-out and imported-session modes remain supported.
- The full automated test suite, Ruff, and mypy must pass before the bolt is completed.

## Constraints

### Technical Constraints

- Extend the current scripted-first `SearchJourney`, offer selection, guarded `BrowserAgent`, and
  `CheckResult` vocabulary instead of introducing a parallel monitoring pipeline.
- The currently observed Booking.com currency preference mechanism must be isolated behind a small
  adapter/helper because its URL or UI representation may drift.
- Rendered page evidence, not a requested URL parameter alone, authorizes price comparison.

### Business Constraints

- The original all-in baseline amount and its ISO-4217 currency remain the comparison baseline.
- A user may edit the baseline explicitly through the existing booking-management flow, but this
  intent never converts or mutates it automatically.

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| Booking.com normally honors a same-site display-currency preference for supported ISO-4217 currencies | VPS continues to see localized currency | Verify rendered candidates, try the visible selector through the guarded agent, then fail closed |
| Candidate extraction exposes enough price/currency evidence after reload | Alignment cannot be verified | Preserve snapshot/trace evidence and return a currency-specific failure |
| The original baseline currency is one the user actually paid or was quoted | Savings comparison may be economically misleading | Keep baseline user-editable and never silently convert or relabel it |

## Open Questions

None. The user approved baseline-currency canonicalization, bounded retry, guarded LLM fallback,
rendered-currency verification, actionable failure reporting, and no FX-based savings decisions.
