---
id: 002-replace-saved-total-with-page-verified-total
unit: 013-confirmation-booked-total
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: "2026-10-10T01:59:26Z"
assigned_bolt: 092-confirmation-booked-total
implemented: true
---

# US-227: Replace a stale saved total with the page-verified total

As a user, I want the price BookSaver compares against to be the one on my confirmation page, not an older wrong figure.

## Acceptance criteria

- A total is marked page-verified only by the code-owned confirmation reader and only when it is an
  explicit all-in total; provider-submitted and merged-with-provider totals are never marked.
- A page-verified total that differs in amount or currency from the saved total replaces it on the
  account reservation and on the monitoring booking in one transaction, keeping the same booking
  identity and check history.
- Savings opportunities computed against the replaced baseline are removed.
- A differing total that is not page-verified still fails the refresh closed without changing any
  saved fact, exactly as today.
- Every other saved-fact conflict rule is unchanged, and other callers' rows are untouched.
