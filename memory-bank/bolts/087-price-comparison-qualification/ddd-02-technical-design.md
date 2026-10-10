---
stage: technical-design
bolt: 087-price-comparison-qualification
created: "2026-10-10T01:47:30Z"
status: complete
---

# Comparison evidence — technical design

The report is read-only and makes no Booking.com or provider call: `booksaver comparison report
[--days N]` (delivered in PR #73 and extended in PR #76) aggregates `price_comparisons` and
`price_comparison_arms` by arm and outcome, with total cost, cost per verified result, average
seconds, the count of pairs where both verified and how many agreed, and recent unverified Jev
runs with their diagnostics. The decision report in the test stage adds per-booking, joint-outcome
and run-order tables from the same tables.

Not built (descoped by the owner's adoption decision, see requirements amendment): percentile
latencies, uncertainty intervals, busy-reject and missed-slot counts, stratification beyond
booking and order.
