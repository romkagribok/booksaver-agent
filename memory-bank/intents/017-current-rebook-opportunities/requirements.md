---
intent: 017-current-rebook-opportunities
phase: inception
status: complete
created: 2026-07-27T02:10:44.000Z
updated: 2026-07-27T02:10:44.000Z
---

# Requirements: Current Rebook Opportunities

## Intent Overview

Correct the Telegram `/rebook` picker so it presents one newest known savings opportunity for each
active booking instead of every historical positive check. A superseded button or manually supplied
historical opportunity ID must fail safely and direct the user back to the current picker.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Remove duplicate and contradictory choices | `/rebook` renders no more than one button for each active booking | Must |
| Prevent stale guided rebooks | A superseded opportunity cannot start a rebook session | Must |
| Preserve useful history | Historical opportunities remain available for audit and diagnostics | Must |
| Preserve multi-booking choice | Each active booking with an opportunity may contribute one button | Must |

## Functional Requirements

### FR-1: Select one newest opportunity per active booking

- **Description**: The Telegram `/rebook` picker must list only the newest persisted savings
  opportunity for each active booking owned by the requesting user.
- **Acceptance Criteria**:
  - Multiple opportunities for one active booking produce exactly one choice.
  - The choice uses the greatest `(validated_at, persistence insertion order)` for that booking.
  - Different active bookings may each produce one choice.
  - Choices are ordered newest validation first across bookings.
  - Archived, deleted, foreign-owned, or missing bookings do not produce choices.
- **Priority**: Must
- **Related Stories**: US-106

### FR-2: Reject superseded selections at execution time

- **Description**: A historical button callback or `/rebook <id>` command must not start a guided
  session after a newer opportunity for the same booking has been persisted.
- **Acceptance Criteria**:
  - Telegram validates freshness before starting its worker.
  - The shared rebook application service validates freshness again before creating a session,
    closing the race between picker rendering and worker execution and protecting CLI callers.
  - A superseded selection creates no rebook session, prompts no cancellation or booking action,
    and produces a clear instruction to run `/rebook` again.
  - The current opportunity continues through the existing ownership and confirmation gates.
- **Priority**: Must
- **Related Stories**: US-107

### FR-3: Preserve audit and access boundaries

- **Description**: Current-choice behavior must be a read/selection policy, not destructive history
  cleanup, and it must preserve all existing ownership and human-action boundaries.
- **Acceptance Criteria**:
  - Historical savings rows, check history, traces, and prior rebook audit records remain stored.
  - `/savings` and operator diagnostics may continue to show historical opportunities.
  - The new query remains scoped through booking ownership and active status.
  - Callback acknowledgements, non-enumerating cross-user errors, one-session-per-user protection,
    and final device-side Booking.com actions remain unchanged.
- **Priority**: Must
- **Related Stories**: US-108

## Non-Functional Requirements

### Reliability

- Selection and freshness ordering must be deterministic when validation timestamps are equal.
- No schema migration, cleanup job, or destructive mutation is introduced.
- A new opportunity arriving after the picker was rendered must make the old button unusable.

### Security and Privacy

- Telegram numeric identity and booking ownership remain authoritative.
- Foreign opportunity identifiers use the existing non-enumerating not-found behavior.
- The correction must not broaden autonomous cancellation, reservation, purchase, or payment.

### Compatibility and Verification

- Existing CLI history listing, Telegram callbacks, rebook confirmations, post-rebook propagation,
  and user scoping remain regression-free.
- Focused persistence, application-service, and Telegram tests plus full pytest, Ruff, mypy,
  diff hygiene, and both AI-DLC validators must pass.

### Performance

- Current-opportunity selection must use one SQLite query. Booking labels may use one bounded batch
  query, never per-booking database round trips.

## Constraints

- “Current” means the newest validated savings opportunity BookSaver already knows for a booking.
  Opening `/rebook` does not run a new Booking.com price check.
- Historical positive opportunities remain append-only until an existing booking lifecycle action
  intentionally removes them.
- Use the existing SQLite store and single-process architecture; add no dependency or service.

## Assumptions and Decisions

- The product owner explicitly requested one latest opportunity per booking and multiple choices only
  for different bookings.
- Retaining history while narrowing actionability best matches ADR-023's separation of durable audit
  evidence from stale actions.
- Freshness must be enforced when starting a session, not only when rendering buttons.
- The product owner authorized uninterrupted AI-DLC construction through final pre-merge review;
  commit, push, merge, and deployment remain held for separate approval.

## Scope Exclusions

- Running `/checknow` automatically from `/rebook`.
- Expiring an opportunity solely because of age or a later failed/non-saving check.
- Changing savings alerts, `/savings` history output, Booking.com extraction, or price comparison.
