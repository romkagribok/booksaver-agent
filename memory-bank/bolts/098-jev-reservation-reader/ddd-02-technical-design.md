---
unit: 001-jev-reservation-reader
bolt: 098-jev-reservation-reader
stage: design
status: complete
created: 2026-11-04T15:35:28Z
updated: 2026-11-04T15:35:28Z
---

# Technical Design - Jev Reservation Reader

- `inventory_confirmation_facts`: remove `_price_facts`, `_cancellation_facts`, the cost-tier and
  refund-schedule parsers, `charge_warning` and the notice constants. Totals and refund terms stay
  `unknown` from code.
- `jev_reservation_facts`: always apply agreed, checked answers; no comparison and no owner notice;
  deadline candidates = cancellation sentences plus dated lines ("until <date>" / "before <date>");
  calendar months for "within"; refund-sentence bar 0.5; unread facts get reason codes for the
  diagnostic.
- Grouped mapping: an explicit Jev total is page-verified again, so ADR-058 replacement applies; the
  bolt-097 Jev-only branches in reconciliation are removed. The source column is still written.
- `render_alert`: the Jev label line is removed. CLI: the owner-notice wiring is removed.

## Test Plan

Jev module checks and settling; parser no longer produces totals or refund terms; reconciliation of a
verified Jev total; alert unchanged without label; staging on the owner's and dad's accounts.

No new ADR beyond ADR-061, which supersedes ADR-060's comparison.
