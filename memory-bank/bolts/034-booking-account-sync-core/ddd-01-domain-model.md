---
unit: 001-booking-account-sync-core
bolt: 034-booking-account-sync-core
stage: model
status: complete
updated: 2026-07-27T16:31:51Z
---

# Static Model - Booking Account Sync Core

## Bounded Context

The **Booking Account Synchronization** context translates one active user's authenticated
Booking.com reservation inventory into read-only local monitoring snapshots. It owns remote
identity, inventory completeness, lifecycle, eligibility, reconciliation, and synchronization
audit. It does not own candidate-price discovery, notifications, or any reservation mutation.

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| `SynchronizedBooking` | local ID, user ID, remote identity, reservation facts, lifecycle, eligibility, freshness, first/last observed | Remote identity is unique per user; facts change only through reconciliation; distinct remote identities never merge |
| `SynchronizationRun` | run ID, user ID, trigger, session revision, started/completed, completeness, outcome, redacted counts | One terminal outcome; incomplete/failed runs cannot authorize absence transitions |
| `InventoryObservation` | remote identity, property, stay, room, occupancy, booked total, refund policy, lifecycle, provenance | Untrusted until validated; may be stored ineligible when identity is valid but monitoring facts are incomplete |
| `EligibilityDecision` | status, ordered reason codes, evaluated snapshot revision | Eligible only with active future refundable hotel state and every trusted search fact |

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| `RemoteReservationId` | opaque normalized value | Non-empty; scoped by user; never emitted raw in logs |
| `ReservationLifecycle` | upcoming, current, completed, cancelled, absent, unknown | External observation only; no BookSaver mutation transition |
| `InventoryCompleteness` | complete, incomplete, failed | Only complete authorizes absence-based reconciliation |
| `SynchronizationTrigger` | connect, session-intake, scheduled, check-now, bookings | Closed vocabulary for audit and orchestration |
| `EligibilityReason` | stable reason code | Closed, deterministic, user-explainable vocabulary |
| `ObservationProvenance` | source, observed time, session revision, extraction method | Redacted; excludes page/session/tracking content |
| `SnapshotRevision` | monotonic local revision | Changes whenever authoritative monitoring facts/lifecycle change |

## Aggregates

| Aggregate Root | Members | Invariants |
|----------------|---------|------------|
| `UserBookingInventory` | synchronization run plus caller's synchronized bookings | Caller scope never changes; remote IDs unique; complete-run reconciliation is atomic; partial run cannot transition unseen members |
| `SynchronizedBooking` | observation, lifecycle, eligibility, freshness | Stable local ID; no user mutation; current savings invalidated whenever monitoring-relevant revision changes |

## Domain Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `BookingDiscovered` | New valid remote identity observed | user, local ID, redacted remote fingerprint, run |
| `BookingSnapshotChanged` | Monitoring-relevant authoritative fact changes | user, booking ID, old/new revision, changed-field categories |
| `BookingBecameAbsent` | Prior booking unseen in complete inventory | user, booking ID, run |
| `BookingEligibilityChanged` | Eligibility status/reasons differ | user, booking ID, old/new decision |
| `SynchronizationCompleted` | Atomic reconciliation commits | user, run, completeness, redacted counts |
| `SynchronizationFailed` | No conclusive commit is possible | user, run, reason category |

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| `BookingEligibilityPolicy` | evaluate observation/snapshot | Clock and existing booking/search value rules |
| `InventoryReconciler` | validate, upsert observed, apply complete-run absence, invalidate stale current savings | Booking inventory repository, opportunity repository, transaction boundary |
| `InventoryObservationValidator` | normalize remote identity and facts; classify ambiguity | Existing domain value objects |

## Repository Interfaces

| Repository | Entity | Methods |
|------------|--------|---------|
| `BookingInventorySource` | inventory observations | `discover(session, user, trigger) -> InventoryResult` |
| `SynchronizedBookingRepository` | synchronized booking | list for user, get by remote ID, reconcile run atomically |
| `SynchronizationRunRepository` | synchronization run | begin, complete/fail, get latest for user |
| `CurrentOpportunityRepository` | current savings | invalidate for changed booking revisions |

## Ubiquitous Language

| Term | Definition |
|------|------------|
| Account inventory | All hotel reservations exposed by the supported authenticated Booking.com journey |
| Observation | Untrusted facts read for one remote reservation during one run |
| Synchronized snapshot | Validated local representation of Booking.com's last conclusive facts |
| Complete run | Traversal that proves every supported inventory page/group was enumerated |
| Partial run | Positive observations without proof that unseen reservations are absent |
| Eligible | Safe to send through the established current-price search |
| Ineligible | Visible reservation that cannot be checked, with explicit reasons |
| Absent | Previously synchronized reservation not observed during a complete run |
| Replacement | Not a BookSaver domain relationship; similar remote reservations remain independent |
