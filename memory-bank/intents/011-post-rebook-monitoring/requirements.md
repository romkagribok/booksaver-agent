---
intent: 011-post-rebook-monitoring
phase: inception
status: complete
created: 2026-07-19T19:50:29.000Z
updated: 2026-07-19T20:23:12Z
---

# Requirements: Post-Rebook Monitoring

## Intent Overview

Close the rebook lifecycle after the device handoff. When a user reports that the replacement
reservation was actually booked, BookSaver must collect the reservation facts that only the final
Booking.com checkout can establish and safely make that reservation the caller's monitored baseline.
The transition must preserve historical evidence, invalidate offers derived from the old baseline,
and explicitly reconcile cases where cancellation or replacement booking was abandoned or unknown.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Continue saving after a successful rebook | The next scheduled/on-demand check uses the actual replacement confirmation, reference, and all-in baseline | Must |
| Avoid false savings and phantom monitoring | No detected offer price is silently treated as paid; cancelled reservations are not left active without a validated replacement | Must |
| Make partial outcomes recoverable | Every cancellation/booking combination produces an explicit durable audit result and actionable user message | Must |

## Functional Requirements

### FR-1: Collect actual replacement reservation facts

- **Description**: After the user reports that the device-side replacement booking completed, collect
  the actual new confirmation ID, a validated same-property Booking.com property URL/reference, and
  the actual final all-in amount and ISO currency from the user.
- **Acceptance Criteria**:
  - The detected savings offer price is displayed only as historical context and is never copied into
    the replacement baseline.
  - Confirmation, URL/reference, and actual total are validated with existing domain value objects
    plus a Booking.com HTTPS/same-property check.
  - Each accepted answer is visibly acknowledged before the next question; a final summary requires
    explicit confirmation before mutation.
  - Invalid input re-prompts without persisting any replacement field.
- **Priority**: Must
- **Related Stories**: US-072

### FR-2: Atomically propagate a valid replacement

- **Description**: Replace the logical reservation represented by the caller-owned monitored booking
  in place, preserving its BookSaver identity and history while changing the actual confirmation,
  property reference, baseline amount/currency, and active status.
- **Acceptance Criteria**:
  - One SQLite transaction revalidates active access, ownership, completed session/opportunity
    linkage, unchanged source snapshot, and confirmation uniqueness before writing.
  - The booking ID, property/stay/room/refundability/occupancy equivalence criteria, registration
    timestamp, check history, traces, and rebook session/events remain intact.
  - Future scheduler and `/checknow` reads immediately observe the actual replacement baseline.
  - A concurrent edit/delete, foreign confirmation conflict, stale opportunity/session, revocation,
    or missing row causes no partial mutation and a non-enumerating failure.
- **Priority**: Must
- **Related Stories**: US-073

### FR-3: Reconcile the complete partial-outcome matrix

- **Description**: Treat old-cancellation and replacement-booking outcomes independently and choose
  the safest monitoring state for every completed, abandoned, or unreported combination.
- **Acceptance Criteria**:
  - Replacement completed + valid confirmed facts activates the replacement baseline regardless of
    cancellation outcome, with an explicit warning when the old cancellation is abandoned/unknown.
  - Old cancellation completed + replacement abandoned/unreported/details abandoned archives the
    old monitored booking and explains that no reservation is currently monitored for the stay.
  - Old cancellation abandoned/unreported + replacement abandoned/unreported leaves the original
    booking unchanged and explains what remains monitored.
  - A session that never sent a replacement handoff cannot propagate a replacement.
  - Restart/cancel during detail collection remains safe: if a completed old cancellation was already
    reported, its archive state is durable; no unconfirmed replacement becomes active.
- **Priority**: Must
- **Related Stories**: US-074

### FR-4: Invalidate stale savings and preserve audit history

- **Description**: Every monitoring reconciliation must remove actionable offers based on a no-longer
  valid baseline while retaining durable evidence of what happened.
- **Acceptance Criteria**:
  - Successful replacement propagation deletes all savings opportunities for the stable booking ID.
  - Archiving a reported-cancelled reservation also deletes its savings opportunities.
  - Check history, traces, rebook sessions, and existing events are retained.
  - An additive audit event records propagation/archive disposition and actual amount/currency without
    logging Telegram messages, bot secrets, or tracking/session query parameters.
- **Priority**: Must
- **Related Stories**: US-075

### FR-5: Preserve ownership, revocation, and visible completion boundaries

- **Description**: Only the still-active owner of the opportunity/booking may answer outcome/detail
  prompts or cause propagation, and every terminal path must tell that user what BookSaver now monitors.
- **Acceptance Criteria**:
  - Ownership and active access are checked before outcome prompts, before starting detail collection,
    and inside the final transaction.
  - Revocation suppresses later prompts/replies and prevents archive/propagation after access loss.
  - Foreign/stale callbacks and guessed identifiers reveal no record existence and mutate nothing.
  - Final messages distinguish replacement monitored, original still monitored, no booking monitored,
    details cancelled, validation failure, and access loss.
- **Priority**: Must
- **Related Stories**: US-076

## Non-Functional Requirements

### Reliability

- Monitoring-state mutation and its audit event must commit or roll back as one SQLite transaction.
- The final transaction must reject a booking whose monitored snapshot changed after handoff.
- Existing daemon restart behavior may discard the in-memory dialog, but durable cancellation
  reconciliation must remain safe and visible through `/bookings`/audit inspection.

### Security and Privacy

- Telegram numeric identity remains authoritative; the owner role does not bypass booking ownership.
- Booking.com references are canonicalized to HTTPS scheme, host, and property path before storage;
  session/tracking query parameters are not retained in the new reference or audit detail.
- Foreign confirmation conflicts use a generic response.

### Compatibility and Verification

- No autonomous Booking.com cancel/purchase action, new dependency, process, or hosted backend.
- Focused outcome/dialog/persistence/revocation tests plus full pytest, Ruff, mypy, diff, and AI-DLC
  artifact validation must pass.

## Constraints

- Preserve ADR-012 device-side final click and the existing rebook confirmation state machine.
- Reuse the stable BookSaver booking ID to retain relational history; do not clone or delete history.
- Do not infer actual checkout amount from the detected opportunity.
- Continue to monitor refundable Booking.com hotel reservations only.

## Assumptions and Decisions

- A user report that the replacement booking completed is necessary but not sufficient; validated
  checkout facts and a final explicit confirmation are also required.
- Property, dates, room, refundability, and occupancy remain the equivalence criteria verified by the
  original opportunity/handoff. The collected Booking.com URL must resolve to the same property path
  when the stored reference supplies one.
- When the user says the old reservation was cancelled, archiving it immediately is safer than
  continuing to check a reservation that no longer exists; a later validated replacement reactivates
  the same aggregate.
- The product owner authorized this intent's AI-DLC flow through implementation and Test, with formal
  bolt completion, commit, push, and deployment held for main-agent review.

## Scope Exclusions

- Verifying the new confirmation against Booking.com's authenticated reservation manager.
- Automatically importing email receipts, scraping checkout, changing stay/room/occupancy during
  propagation, or autonomously cancelling duplicate reservations.
