---
intent: 018-conclusive-rebook-opportunity-lifecycle
phase: inception
status: complete
created: 2026-07-27T02:32:08.000Z
updated: 2026-07-27T02:46:10Z
---

# Requirements: Conclusive Rebook Opportunity Lifecycle

## Intent Overview

Refine the current `/rebook` policy so a technical check failure cannot erase the last successfully
verified saving. A later conclusive market observation must replace that saving when a cheaper
eligible offer still exists, or make it non-actionable when no saving can currently be booked.
Historical checks and savings opportunities remain available for audit.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Preserve useful evidence across automation failures | A later technical failure leaves the last conclusive positive opportunity actionable | Must |
| Never present a superseded quote as current | A later conclusive result controls actionability for its booking | Must |
| Continue showing smaller savings | A newer eligible offer below the paid baseline replaces an older, larger saving | Must |
| Preserve explainability | No check or opportunity history is deleted by current-state selection | Must |

## Functional Requirements

### FR-1: Preserve the last conclusive positive opportunity across technical failures

- **Description**: A failed attempt that does not establish current market availability or price
  must not invalidate the booking's last conclusive positive savings opportunity.
- **Acceptance Criteria**:
  - Authentication, timeout, navigation, extraction, LLM, agent-budget, bot-wall, property-location,
    unresolved currency, rate-limit, and unknown failures do not replace the last conclusive market
    state.
  - `/rebook` continues to show the last positive opportunity after one or more such failures.
  - The opportunity's original validation timestamp and check linkage remain unchanged.
  - Telegram shows that original successful verification time and explains that technical failures
    do not update it.
  - A technical failure does not create, update, or delete a savings-opportunity row.
- **Priority**: Must
- **Related Stories**: US-109

### FR-2: Supersede actionability on a conclusive market observation

- **Description**: The latest conclusive market observation for a booking must determine its
  actionable savings state.
- **Acceptance Criteria**:
  - A successful eligible price below the paid baseline becomes the sole current opportunity even
    when it is higher than the previously observed offer.
  - A successful eligible price equal to or above the paid baseline leaves no current opportunity.
  - `NO_EQUIVALENT_OFFER`, including explicit no availability, leaves no current opportunity.
  - A later successful saving restores actionability after a conclusive non-saving observation.
  - Conclusive ordering uses persisted check-history insertion order, not wall-clock timestamp
    alone.
- **Priority**: Must
- **Related Stories**: US-110

### FR-3: Enforce the conclusive lifecycle at every rebook boundary

- **Description**: Picker listing, manual/callback validation, application-service validation, and
  atomic session creation must agree on the same conclusive-current rule.
- **Acceptance Criteria**:
  - `/rebook` lists at most one opportunity per active owned booking and excludes a positive row
    superseded by a conclusive non-saving result.
  - A historical button or manual opportunity ID cannot start after a conclusive replacement or
    invalidation.
  - The session transaction prevents a conclusive check from racing between validation and insert.
  - Rejection text describes the opportunity as no longer current rather than always claiming a
    newer price exists.
  - Historical `/savings`, check history, traces, notifications, and rebook audit records remain
    unchanged.
- **Priority**: Must
- **Related Stories**: US-111

## Non-Functional Requirements

### Reliability

- Currentness derives from durable check history and opportunity-to-check linkage.
- A technical failure may preserve an old quote, but BookSaver must never rewrite its validation
  time or represent the failed attempt as a successful verification.
- The atomic session guard must serialize against concurrent check-history and opportunity writes.

### Security and Safety

- Existing active-booking, ownership, non-enumeration, confirmation, and device-side final-action
  boundaries remain authoritative.
- Ambiguous failures fail closed as evidence: they cannot invent a new saving or a conclusive market
  outcome.

### Compatibility and Verification

- No schema migration, dependency, cleanup task, external request, or new browser flow.
- Existing savings history, notification, Telegram, CLI, post-rebook, and user-scoping behavior
  remains regression-free.
- Focused persistence, service, Telegram, and pipeline tests plus full pytest, Ruff, mypy, diff
  hygiene, and both AI-DLC validators must pass.

### Performance

- User-scoped current selection remains one SQLite query.
- Single-booking current lookup and atomic session creation remain one query each inside their
  existing transaction boundaries.

## Conclusive-Result Classification

| Persisted result | Conclusive market observation? | Effect on prior opportunity |
|------------------|--------------------------------|-----------------------------|
| `outcome = success`, live price below baseline | Yes | Replace with the newly persisted opportunity |
| `outcome = success`, live price equal/above baseline | Yes | Hide prior opportunity |
| `failure_code = no_equivalent_offer` | Yes | Hide prior opportunity |
| Any other failure code | No | Preserve prior opportunity |

`NO_EQUIVALENT_OFFER` is intentionally treated as conclusive because BookSaver reached the requested
property context and established that no equivalent refundable offer was currently bookable.
Currency mismatch and extraction ambiguity remain non-conclusive.

## Constraints

- Savings and check-history tables remain append-only for normal checks.
- “Current” means the opportunity associated with the latest conclusive market check, if that check
  produced a validated saving.
- `/rebook` does not trigger a live check.

## Assumptions and Decisions

- The product owner explicitly chose evidence preservation across technical failures.
- The comparison that matters is the latest eligible price versus the user's paid baseline, not
  whether the price rose relative to the preceding check.
- The product owner authorized AI-DLC construction through final pre-merge review. Commit, push,
  merge, and deployment remain held for separate approval.

## Scope Exclusions

- Age-based expiry.
- Automatically running `/checknow` from `/rebook`.
- Changing how Booking.com offers are extracted or compared.
- Deleting historical checks or savings opportunities.
