---
bolt: 035-booking-account-sync-core
stage: design
completed: 2026-07-27T17:01:45Z
---

# Technical Design

- Schema v11 performs one immediate SQLite transaction: delete dependent legacy rows, rebuild the
  caller-scoped monitoring projection, and create synchronization-run/account-reservation tables.
- `booking_sync_runs` stores trigger, session revision, completeness, redacted failure, and counts.
- `account_reservations` stores nullable authoritative facts, reason-coded eligibility, stable
  caller-scoped remote hashes, snapshot revision, and optional monitoring projection identity.
- Reconciliation uses `BEGIN IMMEDIATE`; positive observations upsert on partial runs, while only a
  complete run archives unseen monitoring projections and marks their account rows absent.
- Projection fact changes invalidate current savings but retain check history.
