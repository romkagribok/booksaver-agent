---
bolt: 035-booking-account-sync-core
stage: model
completed: 2026-07-27T17:01:30Z
---

# Domain Model

The cutover preserves user identity, access, encrypted session, key, and invite aggregates while
deleting the entire legacy booking aggregate and every dependent check, trace, savings, and rebook
row. A synchronization run is immutable audit evidence; a reservation snapshot may become absent
only after a complete run. Failed and incomplete runs retain the last confirmed snapshot and never
infer lifecycle removal.
