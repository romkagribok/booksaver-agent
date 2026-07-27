---
intent: 019-booking-account-synchronization
phase: inception
status: complete
created: 2026-07-27T14:57:11.000Z
updated: 2026-07-27T22:09:25.000Z
---

# Requirements: Booking Account Synchronization

## Intent Overview

Make the authenticated Booking.com account the sole authority for reservation facts and lifecycle
state. BookSaver synchronizes every visible reservation, explains whether each reservation is
eligible for price-drop monitoring, and retains local snapshots only for scheduling, comparison,
history, and audit.

This intent replaces manual booking registration, editing, deletion, and guided rebooking with
read-only account synchronization. Users make all reservation changes, cancellations, and
replacement bookings directly in Booking.com.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Remove duplicate booking data entry | No user-entered reservation facts are required for normal operation | Must |
| Make current account state visible | Every future upcoming reservation is shown with monitoring eligibility status | Must |
| Keep monitoring safe | Only complete, active, refundable hotel reservations are checked for price drops | Must |
| Eliminate competing sources of truth | No normal BookSaver command can create, edit, delete, cancel, or replace synchronized reservation facts | Must |
| Simplify rebooking | BookSaver detects and reports savings; the user performs all booking and cancellation actions independently in Booking.com | Must |

## Approved Product Direction

- Synchronize after `/connect`, before scheduled checks, before `/checknow`, and when `/bookings` is
  requested.
- Fetch and synchronize every reservation exposed by the supported authenticated account journey.
- Display only future upcoming reservations in `/bookings`, including future reservations that are
  not eligible for monitoring, and explain every displayed ineligible reservation with a
  user-visible reason.
- Retire Telegram booking registration, editing, deletion, and guided rebooking commands and flows.
- Treat Booking.com as authoritative; local reservation records are synchronized snapshots, not
  user-editable truth.
- Reconcile explicit changes and cancellations automatically; fail closed when account state is
  incomplete or ambiguous.
- Never infer that similar reservations are replacements for one another and never autonomously
  cancel, reserve, purchase, pay, or modify a Booking.com reservation.

## Scope

### In Scope

- Authenticated account inventory discovery and reconciliation.
- Complete and partial synchronization semantics.
- Eligibility classification and visible reason codes.
- Trigger integration with `/connect`, `/bookings`, `/checknow`, and scheduled checks.
- Retirement of manual booking CRUD and guided-rebook behavior.
- Destructive cutover removal of existing legacy bookings and their dependent local history.
- User-scoped security, privacy, observability, failure recovery, and browser cleanup.

### Out of Scope

- Autonomous reservation creation, cancellation, payment, purchase, or modification.
- Inferring replacement relationships between separate Booking.com reservations.
- Using reservation-management pages as live comparison-price sources.
- Native Booking.com app automation, email receipt import, or private API reverse engineering.
- Construction or application-code changes before human approval of the inception artifacts.

## Functional Requirements

### FR-1: Synchronize the complete authenticated hotel-reservation inventory

- **Description**: BookSaver must use the active user's authenticated Booking.com session to
  discover every hotel reservation exposed by the supported account inventory journey, regardless
  of whether the reservation is eligible for price-drop monitoring.
- **Acceptance Criteria**:
  - A conclusive inventory traversal follows supported pagination or grouping until it can prove the
    account inventory is complete for the supported hotel-reservation scope.
  - Upcoming, current, past, cancelled, non-refundable, incomplete, and otherwise ineligible hotel
    reservations returned by the journey are synchronized for reconciliation, history, and audit.
  - Historical, current-stay, cancelled, absent, and missing-date reservations are not exposed by
    `/bookings`; the command is a future-upcoming reservation view.
  - BookSaver's per-user monitoring cap or daily check allowance never hides or prevents
    synchronization of an account reservation.
  - Non-hotel Booking.com products remain outside the BookSaver product scope and are never treated
    as hotel reservations eligible for price checks.
  - The synchronization flow performs read-only account navigation and never opens or submits a
    cancellation, modification, reservation, checkout, or payment action.
- **Priority**: Must
- **Related Stories**: Pending story decomposition

### FR-2: Preserve remote identity and synchronized local snapshots

- **Description**: Each Booking.com reservation must have a caller-scoped remote identity and a
  locally stable BookSaver identity. Local state is a synchronized snapshot used for monitoring,
  history, and audit; it is not an independently editable reservation record.
- **Acceptance Criteria**:
  - Repeated observation of the same caller-owned Booking.com reservation updates the same local
    aggregate instead of creating a duplicate.
  - Reservations with similar property, dates, room, or occupancy remain separate when Booking.com
    exposes distinct remote reservation identities.
  - A synchronized snapshot records the reservation facts needed by the existing domain model:
    property identity/reference, stay dates, room type, booked all-in total and currency,
    refundability terms/deadline, occupancy, confirmation identity, and remote lifecycle status.
  - Every snapshot records redacted provenance including user, synchronization run, source kind,
    observation time, session revision, and extraction method.
  - Tracking/session query parameters and unnecessary account-page content are not retained.
  - No user-facing BookSaver path can overwrite synchronized reservation facts.
- **Priority**: Must
- **Related Stories**: Pending story decomposition

### FR-3: Classify and explain monitoring eligibility

- **Description**: BookSaver must evaluate every synchronized reservation and show whether it is
  eligible for price-drop monitoring, with stable, user-visible reasons for every ineligible or
  indeterminate result.
- **Acceptance Criteria**:
  - A reservation is eligible only when it is an active future Booking.com hotel reservation,
    demonstrably refundable, and has all trusted facts required for an equivalent, currency-aligned
    customer-search check.
  - Eligibility is recalculated from the newest conclusive synchronized snapshot.
  - Ineligibility reasons distinguish at least: past/completed, cancelled, non-refundable,
    refundability unknown, unsupported reservation/product type, missing property identity, missing
    stay dates, missing room type, missing occupancy, missing booked total/currency, ambiguous
    extraction, not observed in the latest complete inventory, and unmatched legacy record.
  - Multiple applicable reasons may be retained and displayed; BookSaver never guesses a missing
    value to make a reservation eligible.
  - Authentication or synchronization failures mark freshness separately and do not mislabel a
    previously eligible reservation as cancelled or non-refundable.
  - Monitoring limits and temporary execution failures are shown separately from intrinsic booking
    eligibility.
- **Priority**: Must
- **Related Stories**: Pending story decomposition

### FR-4: Synchronize at every approved freshness boundary

- **Description**: Account synchronization must run after successful session intake, before
  monitoring work, and when the user asks to view bookings.
- **Acceptance Criteria**:
  - A successful Telegram `/connect` session capture triggers caller-scoped synchronization and
    reports its result.
  - Existing non-Telegram session-intake paths trigger the same synchronization behavior so
    self-hosted laptop operation is not left with a manual booking source of truth.
  - Each scheduled run synchronizes an active user once before planning or executing that user's
    booking checks; it does not repeat the inventory traversal per booking.
  - `/checknow` synchronizes the caller before resolving and checking the requested reservation.
  - `/bookings` starts a fresh caller-scoped synchronization before rendering the resulting account
    inventory.
  - Synchronization shares the existing browser coordinator/lease with scheduled and on-demand work,
    has a bounded timeout, and never creates unbounded queued browser work.
  - Price checking proceeds only from the conclusive synchronization result produced for that
    trigger; a failed or indeterminate prerequisite synchronization causes the affected checks to
    fail closed with visible recovery guidance.
- **Priority**: Must
- **Related Stories**: Pending story decomposition

### FR-5: Reconcile account changes without false deletion or replacement inference

- **Description**: BookSaver must reconcile observed Booking.com state into local snapshots
  idempotently and atomically while distinguishing a complete account inventory from partial
  evidence.
- **Acceptance Criteria**:
  - A synchronization run explicitly records whether inventory enumeration was complete,
    incomplete, or failed.
  - Positively observed reservations may be inserted or updated during a complete or partial run.
  - A reservation may be marked absent/not-observed because it was missing from the account only
    after a conclusive complete traversal; a partial or failed run cannot make an unseen reservation
    inactive, cancelled, deleted, or absent.
  - An explicit Booking.com cancelled, completed, or past status may make that observed reservation
    ineligible without relying on inventory absence.
  - Changed dates, room, occupancy, refund terms, property identity, booked total, currency, or
    lifecycle status update the same remote reservation's stable local aggregate and invalidate any
    actionable savings evaluated against the previous snapshot.
  - Cancelled, past, and absent reservations remain available for user visibility and audit rather
    than being physically deleted.
  - Distinct old and replacement reservations are shown independently. BookSaver never infers a
    replacement relationship, merges their histories, or takes action on either reservation.
  - One per-user transaction commits the new snapshots, eligibility, currentness invalidation, and
    synchronization audit or rolls them back together.
- **Priority**: Must
- **Related Stories**: Pending story decomposition

### FR-6: Preserve the verified live-price source boundary

- **Description**: Reservation-management pages provide authoritative booked facts and lifecycle
  state only. Live comparison prices must continue to come exclusively from the verified
  authenticated customer-search journey.
- **Acceptance Criteria**:
  - A reservation's synchronized booked all-in total and currency form the paid baseline only when
    both are conclusively extracted from Booking.com's reservation facts.
  - No price displayed on an account/reservation-management page is accepted as a currently
    bookable replacement offer.
  - Each eligible check uses the newest snapshot from its prerequisite synchronization to construct
    the existing property/date/room/occupancy/currency search.
  - Candidate offers still pass existing same-property, same-dates, same-room, same-occupancy,
    refundable, all-in-total, currency, authentication, provenance, and action-guard requirements.
  - Missing or ambiguous synchronized facts produce an eligibility reason and no price check.
- **Priority**: Must
- **Related Stories**: Pending story decomposition

### FR-7: Make `/bookings` the synchronized reservation-status experience

- **Description**: `/bookings` must become the primary user experience for refreshing and
  understanding the user's Booking.com reservation inventory.
- **Acceptance Criteria**:
  - The command promptly acknowledges that synchronization is running and later edits or sends a
    bounded result when browser work completes.
  - The result includes every synchronized reservation whose remote lifecycle is upcoming and whose
    check-in date is later than the current UTC date, in a bounded, paginated, or button-selectable
    presentation that respects Telegram message and callback limits.
  - Completed, past, current-stay, cancelled, absent, and missing-date reservations remain
    synchronized internally but are omitted from `/bookings`.
  - Each reservation summary shows recognizable property/dates, remote lifecycle state, monitoring
    eligibility, all applicable ineligibility reasons, and last successful observation time.
  - Eligible reservations provide applicable read-only actions such as viewing current savings or
    requesting `/checknow`; ineligible reservations do not expose a price-check action.
  - Authentication failure presents a caller-scoped `/connect` recovery action.
  - No booking summary or detail view exposes an edit, local delete, Booking.com cancel, guided
    rebook, or manual replacement-facts action.
- **Priority**: Must
- **Related Stories**: Pending story decomposition

### FR-8: Retire manual booking mutation paths

- **Description**: Manual registration, editing, and local deletion must be retired because they
  create a competing source of reservation truth.
- **Acceptance Criteria**:
  - `/register`, `/editbooking`, and `/deletebooking` are removed from Telegram command catalogs,
    `/help`, inline keyboards, callback routes, dialog registration, and normal documentation.
  - Typed use of a retired Telegram command is unknown immediately; no compatibility alias or
    explanatory no-op handler remains.
  - Normal CLI/application paths cannot create, edit, delete, archive, or reactivate a synchronized
    reservation; session intake and booking inspection remain available.
  - No operator-only booking mutation or legacy migration mechanism remains.
  - Generic `/cancelflow` remains only where required to abort unrelated surviving dialogs; it has
    no booking-mutation or rebooking semantics.
  - Booking facts can change only through a later conclusive observation of the same caller-owned
    Booking.com reservation.
- **Priority**: Must
- **Related Stories**: Pending story decomposition

### FR-9: Retire guided rebooking while preserving useful savings

- **Description**: BookSaver must remain a monitor and notifier but must no longer orchestrate,
  confirm, record, or reconcile a guided rebooking workflow.
- **Acceptance Criteria**:
  - `/rebook`, rebook-selection callbacks, confirmation gates, manual outcome prompts, replacement
    detail dialogs, device-handoff orchestration, and new rebook-session creation are removed from
    user-facing behavior.
  - Savings notifications and `/savings` continue to explain the verified opportunity and may link
    to a non-mutating Booking.com customer-search or property destination for independent user
    action.
  - BookSaver never asks whether the old reservation was cancelled or whether a replacement was
    booked; subsequent account synchronization observes each reservation independently.
  - Existing legacy rebook session/event history is removed with legacy bookings at cutover; no new
    rebook session or event is created afterward.
  - When synchronization changes a reservation's authoritative snapshot or lifecycle, savings based
    on the old snapshot become non-actionable while historical evidence remains.
  - BookSaver never cancels an old reservation, books a replacement, merges two reservations, or
    decides which of two similar reservations the user intended to keep.
- **Priority**: Must
- **Related Stories**: Pending story decomposition

### FR-10: Remove legacy booking state at cutover

- **Description**: Existing manually registered or previously propagated booking state must be
  removed rather than matched into the synchronized account model because the deployment has no
  active users and Booking.com will repopulate authoritative reservations.
- **Acceptance Criteria**:
  - The schema migration atomically deletes all pre-cutover booking rows and booking-scoped check,
    trace, savings, rebook-session, rebook-event, and related dependent rows.
  - User, invite, encrypted session, API-key, usage, and access-control records are preserved.
  - The migration is idempotent and cannot leave orphaned booking-scoped rows.
  - The first post-cutover conclusive synchronization creates fresh stable local identities solely
    from the caller's remote Booking.com reservations.
  - No legacy matching, import, fallback, audit display, or operator mutation path remains.
  - The deployment runbook requires a recoverable SQLite backup before applying the destructive
    cutover migration.
- **Priority**: Must
- **Related Stories**: Pending story decomposition

### FR-11: Recover visibly from authentication and extraction failures

- **Description**: Synchronization failures must preserve the last confirmed evidence, prevent unsafe
  checks or reconciliation, and tell the affected user how to recover.
- **Acceptance Criteria**:
  - Expired/missing authentication, bot walls, rate limits, timeouts, navigation failures,
    unsupported layouts/locales, incomplete pagination, extraction ambiguity, and persistence
    conflicts have distinct redacted outcomes.
  - A failed or incomplete run retains previously synchronized records and historical eligibility,
    marks freshness as stale/unknown, and performs no absence-based lifecycle mutation.
  - Authentication-required outcomes use the existing deduplicated reconnect notification and
    caller-scoped `/connect` action.
  - Other retryable failures tell the user to retry `/bookings` or `/checknow` without requesting
    manual reservation facts.
  - Repeated failures remain visible to the operator through redacted logs, status, and health
    reporting without disclosing reservation contents across users.
- **Priority**: Must
- **Related Stories**: Pending story decomposition

## Non-Functional Requirements

### Security and Privacy

- **User isolation**: 100% of inventory reads, snapshot writes, Telegram displays, synchronization
  runs, and checks resolve the still-active caller and that caller's encrypted Booking.com session;
  there is zero owner/global/public/cross-user fallback.
- **Read-only account automation**: The inventory adapter exposes no mutation operation, and the
  existing action guard blocks cancellation, modification, reservation, checkout, payment, account
  settings, and final booking targets.
- **Sensitive identifiers**: Full confirmation/reservation identities, session material, and
  account-page content are excluded from logs, traces, metrics, Telegram list summaries, and error
  messages unless a narrowly necessary caller-visible detail is explicitly redacted.
- **Local control**: Synchronized reservations, session state, snapshots, and audit remain on the
  owner-operated host under existing encrypted-session and local-persistence boundaries.

### Reliability and Data Integrity

- **Atomicity**: Each conclusive per-user reconciliation and its current-savings invalidation commits
  or rolls back as one transaction.
- **Idempotency**: Repeating the same inventory observation produces no duplicate reservation,
  duplicate lifecycle transition, or duplicate user notification.
- **Completeness safety**: Zero absence-based reservation transitions originate from a partial or
  failed inventory run.
- **Evidence retention**: Post-cutover synchronized snapshots, checks, and savings survive normal
  reconciliation; explicitly removed pre-cutover legacy booking history is not retained.
- **Restart safety**: A process restart during synchronization leaves either the previous conclusive
  inventory or a fully committed new inventory; it never exposes a half-reconciled account.

### Performance and Resource Control

- `/bookings`, `/connect`, and `/checknow` acknowledge accepted browser work within 2 seconds under
  normal Telegram API conditions, without waiting synchronously for Booking.com navigation.
- One inventory traversal is performed per user per trigger batch, not once per reservation.
- Synchronization uses the existing bounded browser lease, configurable check timeout, cancellation,
  daily resource controls, and clean context/process teardown.
- Large inventories use bounded pagination and persistence batches without exceeding Telegram
  payload limits or creating unbounded in-memory page content.

### Observability and Explainability

- Each run records a redacted run ID, caller ID, trigger, start/end time, completeness, outcome,
  counts discovered/inserted/updated/unchanged/eligible/ineligible/stale, reason-code counts,
  extraction method, and cleanup result.
- User-visible output distinguishes intrinsic ineligibility, stale account state, authentication
  failure, monitoring quota, and technical check failure.
- Operators can diagnose the last synchronization outcome without seeing another user's property,
  confirmation, dates, price, or session data.

### Compatibility and Verification

- Existing invite/owner access, encrypted sessions, authenticated search, price-equivalence gates,
  currency alignment, savings notifications, fair scheduling, and current-opportunity semantics
  remain intact except where this intent explicitly retires mutation/rebook behavior.
- Construction must include focused domain, persistence, browser-adapter, Telegram, migration,
  concurrency, revocation, and failure tests plus the full Ruff, mypy, and pytest gates.
- Acceptance requires real authenticated Booking.com/VPS smoke testing with multiple reservation
  states, pagination where available, `/connect`, `/bookings`, `/checknow`, scheduled execution,
  process status, logs, health, browser cleanup, and verification that no reservation mutation
  occurred.

## Constraints

### Technical Constraints

- Preserve the single-process, synchronous Playwright, hexagonal, stdlib-first architecture and
  existing browser coordinator unless a later reviewed ADR explicitly changes them.
- Use Booking.com's rendered authenticated customer/account UI through bounded browser automation;
  do not reverse engineer private APIs, bypass platform protections, or collect raw account
  passwords.
- Treat page content and any bounded LLM interpretation as untrusted; domain validation and adapter
  guards remain authoritative.
- Reservation/account pages are booking-fact sources only; live candidate prices remain sourced from
  the verified customer-search journey.
- The first live VPS discovery prototype is a feasibility gate because Booking.com layouts,
  pagination, localization, and datacenter-IP behavior are external uncertainties.

### Business Constraints

- Price-drop monitoring remains limited to refundable Booking.com hotel reservations.
- All booking, cancellation, modification, payment, and purchase actions remain entirely outside
  BookSaver and under the user's direct control in Booking.com.
- No BookSaver-operated backend or third-party reservation/session processor may be introduced.

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| Booking.com's authenticated account UI exposes stable reservation identity and the required booked facts | Reservations cannot be matched or made eligible safely | Start construction with a read-only live-account spike; retain visible ineligible records and fail closed |
| The supported account journey can prove pagination/inventory completeness | Missing items could be mistaken for removed reservations | Model completeness explicitly; prohibit absence-based transitions for partial runs |
| Booked all-in total, currency, room, occupancy, and refundability are rendered for eligible reservations | Some reservations cannot drive equivalent searches | Display the reservation with precise missing-fact reasons; do not request manual corrections |
| A user's account may contain old and replacement reservations simultaneously | Automatic replacement inference could destroy or hide a valid booking | Keep every remote identity independent and take no cancellation/merge action |
## Open Questions for Construction Design

| Question | Resolution Gate |
|----------|-----------------|
| Which Booking.com account routes, page variants, pagination controls, and stable reservation identifiers are supportable on the real VPS? | Read-only discovery spike before domain implementation |
| Which locale(s) can be supported deterministically in the first release, and where may bounded LLM interpretation assist without deciding eligibility? | Spike evidence and technical-design review |
