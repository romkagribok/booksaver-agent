---
bolt: 036-synchronized-booking-interface
stage: model
completed: 2026-07-27T17:02:22Z
---

# Domain Model

Synchronization is a freshness boundary owned by the single browser gate. `/connect`, scheduled
monitoring, `/checknow`, and `/bookings` identify the caller and trigger a caller-scoped run.
`/bookings` renders only reservations whose synchronized lifecycle is upcoming and whose check-in
date is later than the current UTC date. Completed, past, current-stay, cancelled, absent, and
missing-date records remain synchronized internally. Future ineligible reservations remain visible
with reasons. The command surface contains no booking mutation or rebooking intent.
