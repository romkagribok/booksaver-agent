---
intent: 041-desktop-price-trial
phase: inception
status: context-defined
created: "2026-11-13T03:02:27Z"
updated: "2026-11-13T03:02:27Z"
---

# One-week silent desktop price trial - System Context

## System Overview

A scheduled slot checks each of a user's bookings on mobile web (unchanged). For a trial user the
slot then reopens each checked booking's property page in a desktop Chromium profile with the same
saved session, runs the same Jev reading, validators and offer selection, and stores the outcome in
`desktop_trial_readings`. Nothing else reads that table.

## Context Diagram

```text
scheduled slot (one user, execution gate held)
  -> inventory sync -> mobile check per booking -> history, savings, alerts   (unchanged)
  -> trial user and before ends_on?
       -> per checked booking: desktop profile + saved session (read only)
            -> Jev reading -> validators -> offer selection
            -> desktop_trial_readings (check_id of the mobile check)
```

## External Integrations

- **Booking.com desktop web**: one extra signed-in property page per checked booking per slot.
- **TypeSafe (Jev)**: one extra capped run per reading, recorded in `jev_price_runs` as
  `jev-price-desktop-trial`.

## High-Level Constraints

- One browser at a time (ADR-021); mobile web remains the only result-producing source (ADR-025).

## Key NFR Goals

- The trial user's checks, history, alerts, limits and session are the same with and without it.
