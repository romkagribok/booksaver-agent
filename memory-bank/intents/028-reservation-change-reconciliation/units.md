---
intent: 028-reservation-change-reconciliation
phase: inception
status: units-decomposed
created: "2026-11-02T20:51:19Z"
updated: "2026-11-02T20:51:19Z"
---

# Reservation change reconciliation - Unit Decomposition

## Units Overview

### Unit 1: 001-reservation-change-sync

Accept code-read changes, clear stale facts, read the total, invalidate savings. Bolt
`093-reservation-change-sync`, stories US-226 to US-228. FR-1 to FR-5.

### Unit 2: 002-jev-currency-pin

Keep the Jev page in the booked currency. Bolt `094-jev-currency-pin`, story US-229. FR-6.

### Unit 3: 003-monitoring-stall-notice

Tell a user when a reservation stops being monitored and when it recovers. Bolt
`095-monitoring-stall-notice`, stories US-230 and US-231. FR-7 and FR-8.

## Unit Dependency Graph

```text
001-reservation-change-sync   (independent, released together with 002)
002-jev-currency-pin
003-monitoring-stall-notice   (after 001 and 002 are released)
```

## Execution Order

Units 1 and 2 restore monitoring and ship in one release, because the booking verifies only with
both. Unit 3 follows.
