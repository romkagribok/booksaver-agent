---
unit: 003-monitoring-stall-notice
bolt: 095-monitoring-stall-notice
stage: design
status: complete
created: 2026-11-03T01:27:07Z
updated: 2026-11-03T01:27:07Z
---

# Technical Design - Monitoring Stall Notice

## Domain (`domain/monitoring_stall.py`)

`MonitoredReservation` and `stall_reason(reservation, now)`, pure and free of I/O. Hold is recognized
from eligibility reasons: any missing-fact reason and no non-refundable reason.

## Persistence (`persistence/monitoring_stall.py`, schema v22)

Additive table `monitoring_stall_notices(booking_id PK, user_id, reason, notified_at)`, removed in
user purge. `SqliteMonitoringStallRepository` lists monitored reservations with their last conclusive
result and the latest sync outcome, and reads, records and deletes notices.

## Coordinator

`run_scheduled_slot` calls `_report_monitoring_stalls` in its `finally`, before completing the slot,
in its own connection and `try`, so a reporting failure cannot strand a slot or affect a check.
Delivery uses the same direct `TelegramNotifier` path as the daily-limit notice, to the reservation's
own user. Only scheduled runs evaluate; `/checknow` results count as conclusive results.

## Test Plan

Domain boundaries and reasons; repository queries and user scoping; coordinator: one notice, no
repeat across a new coordinator, recovery, new stall, session not ready, failed send retried, slot
completes when reporting raises. A dry run on a production snapshot counts who would be notified on
the first run.

No ADR: this adds a notification on the existing path and changes no recorded decision.
