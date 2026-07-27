---
unit: 001-booking-account-sync-core
bolt: 034-booking-account-sync-core
stage: design
status: complete
updated: 2026-07-27T16:32:57Z
---

# Technical Design - Booking Account Sync Core

## Architecture Pattern

Extend the existing hexagonal single-process architecture with a read-only inventory source port and
an atomic reconciliation application service. Persist the full account inventory separately from
the existing strict `Booking` aggregate:

- `account_reservations` is the authoritative synchronized read model and permits incomplete,
  cancelled, past, or unsupported observations.
- `bookings` remains a derived monitoring projection containing only complete eligible reservations
  and continues feeding the established search/savings pipeline.
- Reconciliation is the only writer from account reservation to monitoring projection.

This avoids weakening required `Booking` invariants while removing all manual writers.

## Layer Structure

```text
Telegram / Scheduler / Session Intake
                 |
                 v
      SynchronizeBookingAccount
        |        |          |
        v        v          v
 Inventory     Eligibility  Atomic Inventory
 Source Port    Policy      Repository Port
        |                       |
        v                       v
 Booking.com UI Adapter      SQLite Adapter
                                |
                                v
                       Existing Booking/Search/
                         Savings Projections
```

## Application Contracts

### Inventory source

```python
class BookingAccountInventorySource(Protocol):
    def discover(
        self,
        *,
        user_id: str,
        session: BrowserSession,
        trigger: SynchronizationTrigger,
    ) -> InventoryDiscoveryResult: ...
```

`InventoryDiscoveryResult` contains:

- `observations: tuple[ReservationObservation, ...]`
- `completeness: complete | incomplete | failed`
- `failure: SynchronizationFailure | None`
- redacted traversal/provenance metadata

### Synchronization use case

```python
class SynchronizeBookingAccount:
    def execute(user_id, trigger) -> SynchronizationReport: ...
```

The use case resolves current access/session, calls the inventory source, validates/deduplicates
observations, evaluates eligibility, and passes one reconciliation command to persistence.

### Reconciliation repository

```python
class AccountReservationRepository(Protocol):
    def reconcile(
        self,
        *,
        user_id: str,
        run: SynchronizationRun,
        reservations: tuple[ReconciledReservation, ...],
    ) -> ReconciliationSummary: ...
```

## Data Persistence

### `booking_sync_runs`

- `run_id` primary key
- `user_id` foreign key
- `trigger`, `started_at`, `completed_at`
- `completeness`, `outcome`, `failure_code`
- redacted aggregate counts and `session_revision`

### `account_reservations`

- `account_reservation_id` stable local UUID primary key
- `user_id` foreign key
- `remote_key_hash` deterministic caller-scoped SHA-256 fingerprint, unique with `user_id`
- nullable normalized reservation facts required for display/eligibility
- `remote_lifecycle`, `eligibility_status`, JSON-encoded ordered `eligibility_reasons`
- `snapshot_revision`, `first_observed_at`, `last_observed_at`, `last_sync_run_id`
- `monitoring_booking_id` nullable foreign key to the derived strict booking projection

The raw remote key is ephemeral and never logged. The existing confirmation identity remains only
where required for the strict eligible projection.

### Schema v11 cutover

One migration:

1. Delete all booking-scoped dependent rows and legacy `bookings`.
2. Preserve users, invites, encrypted sessions, API keys, and access/usage state.
3. Create synchronization tables/indexes and any projection-link columns.
4. Verify foreign keys and idempotent schema version.

The operations runbook requires an online SQLite backup before upgrade.

## Reconciliation Algorithm

1. Reject duplicate remote fingerprints within one discovery result as incomplete/ambiguous.
2. Upsert every validated positive observation for the caller.
3. Derive ordered eligibility reasons.
4. For eligible observations, create/update/reactivate one strict monitoring projection.
5. For newly ineligible observations, archive any existing projection and invalidate current savings.
6. Only for `complete` discovery, mark prior unseen account reservations `absent`, archive their
   projections, and invalidate current savings.
7. Persist the run, account rows, projections, and invalidations in one immediate transaction.
8. For incomplete/failed discovery, never apply absence transitions; failed discovery writes only a
   redacted run result.

## Browser Inventory Adapter

- Restore only the caller's validated encrypted session into a fresh Android-like Chromium context.
- Navigate to the allowlisted Booking.com reservation/account inventory entry.
- After `domcontentloaded`, wait within a fixed timeout for a stable rendered card, explicit empty
  state, structured reservation payload, or signed-out state; never snapshot a loading skeleton as
  inventory evidence.
- Parse scripted DOM/embedded structured data first and follow allowlisted pagination/detail links.
- Keep a visited set and hard page/item/action limits.
- Report `complete` only when every pagination link terminates and either explicit all-scope
  evidence is rendered or upcoming, past, and cancelled scopes are each traversed successfully.
- Return `incomplete` for unknown layouts, duplicate remote IDs, missing terminal evidence, or
  partially readable pages.
- Reuse the existing signed-in verification and action guard; expose navigation/extraction only.
- Optional bounded LLM interpretation may map text into candidate fields but cannot create remote
  identity, assert completeness, decide eligibility, or select actions.

## Security Design

| Concern | Approach |
|---------|----------|
| Caller isolation | Resolve active user and encrypted session before opening context; repositories require user ID |
| Remote identity | Persist caller-scoped hash; redact raw identity from diagnostics |
| Browser actions | Allowlisted account navigation/extraction plus existing mutation denylist |
| Partial evidence | Completeness is explicit and required for absence |
| Source confusion | Account UI provides baseline facts only; customer search provides candidates |
| Persistence | Immediate transaction, foreign keys, unique caller/remote fingerprint |

## NFR Implementation

| Requirement | Design Approach |
|-------------|-----------------|
| Idempotency | Unique `(user_id, remote_key_hash)` and snapshot comparison |
| Atomicity | One SQLite immediate transaction per reconciliation |
| Bounded work | Existing browser lease plus page/item/action/time limits |
| Explainability | Stable enums, ordered reasons, redacted run counts |
| Restart safety | No durable partial state outside terminal transaction |
| Testability | Fake inventory source, pure eligibility policy, fixture-backed DOM adapter |

## Error Handling

Failures are stable categories: `auth_required`, `bot_wall`, `rate_limited`, `timeout`,
`navigation_failed`, `unsupported_layout`, `pagination_incomplete`, `identity_ambiguous`,
`extraction_ambiguous`, `persistence_conflict`, and `unknown`. Only positive observations from an
incomplete run may reconcile; no failed run changes reservation state.

## Verification Strategy

- Pure tests for eligibility, remote fingerprinting, completeness, duplicate identity, and snapshot
  changes.
- SQLite integration tests for cutover, idempotent upsert, caller isolation, atomic rollback,
  absence gating, projection archive/reactivation, and savings invalidation.
- Fixture-backed browser extraction tests for empty/single/multiple/paginated/partial/auth-wall
  inventories.
- Real authenticated VPS acceptance remains a release gate before deployment/merge approval.
