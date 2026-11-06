---
stage: implement
bolt: 102-trip-count-ignores-cancelled
created: 2026-11-06T00:21:42Z
---

# Implementation Walkthrough

`GroupedInventoryReader.count_matches` accepts the trip page when all status cards plus non-hotels,
or the non-cancelled, non-completed ones plus non-hotels, equal the trip count. The wait loop,
`count_verified` and `reservation_targets` use it; cancelled cards remain in the read list.
