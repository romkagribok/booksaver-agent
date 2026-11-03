---
intent: 028-reservation-change-reconciliation
phase: inception
status: context-defined
created: "2026-11-02T20:51:19Z"
updated: "2026-11-02T20:51:19Z"
---

# Reservation change reconciliation - System Context

## System Overview

The grouped inventory reader's code-owned parser already reads the changed facts. The observation
now also says they were code-read, and persistence accepts them where it used to raise a conflict,
clearing stale facts. The Jev method pins the page currency after Booking.com's redirect. The
coordinator evaluates stalls after each scheduled run and notifies through the existing per-user
Telegram path.

## Context Diagram

```text
Booking.com reservation page -> grouped reader -> confirmation parser (approx. line accepted)
   -> observation (stay facts verified) -> account_reservations -> bookings -> saved opportunities removed
Booking.com property page -> redirect -> re-open with selected_currency -> Jev offers -> select_offer
Scheduled run -> stall evaluation -> persisted notice state -> Telegram to the reservation's own user
```

## External Integrations

None added. Booking.com through the existing session; Telegram through the existing notifier.

## Data

One small addition for FR-8: durable per-booking stall notice state (schema version taken at
implementation time after re-checking open pull requests).
