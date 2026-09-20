---
id: 002-distinguish-cancellation-and-unverified-records
unit: 012-trusted-inventory-reconciliation
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: "2026-09-19T22:04:01Z"
assigned_bolt: 077-trusted-inventory-reconciliation
implemented: true
---

# US-193: Distinguish cancellations, replacements and unverified records

As a user, I want the list to explain what was checked and to distinguish my cancelled booking from its replacement.

## Acceptance criteria

- Explicit cancellation applies only to the exact caller-bound confirmation observed cancelled; preserve
  financial/history facts and prevent a cancelled row from producing an active monitoring projection.
- A different confirmation remains a different reservation even for identical property and dates;
  no semantic matching transfers cancellation, monitoring authority or terms between the two.
- Incomplete refreshes label preserved, unseen rows as saved and unverified, not current confirmed
  reservations. Current-run positives may be reported separately without claiming full coverage.
- Complete refreshes remove retired rows from active choices and accurately report empty/updated lists.
  Explain absence as no longer on the current list, not cancelled unless explicitly observed.
- Authentication success is not inventory/price success; raw reason codes and internal jargon stay out
  of user-facing refresh copy. Scheduled/manual flows retain the same caller and receipt boundaries.
