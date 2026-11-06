---
stage: plan
bolt: 102-trip-count-ignores-cancelled
created: 2026-11-05T23:59:59Z
---

# Implementation Plan

One helper in `grouped_inventory_reader.py` decides whether a trip page's cards match its count:
all status cards plus non-hotels, or active status cards plus non-hotels. The wait loop, the
`count_verified` check and `reservation_targets` use it. Cancelled cards stay in the read list.
Tests: the captured trip shape, a non-matching count, and the existing count tests.
