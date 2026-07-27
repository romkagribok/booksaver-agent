---
bolt: 036-synchronized-booking-interface
stage: model
completed: 2026-07-27T17:02:22Z
---

# Domain Model

Synchronization is a freshness boundary owned by the single browser gate. `/connect`, scheduled
monitoring, `/checknow`, and `/bookings` identify the caller and trigger a caller-scoped run.
`/bookings` renders every synchronized lifecycle, including cancelled, completed, ineligible, and
absent records. The command surface contains no booking mutation or rebooking intent.
