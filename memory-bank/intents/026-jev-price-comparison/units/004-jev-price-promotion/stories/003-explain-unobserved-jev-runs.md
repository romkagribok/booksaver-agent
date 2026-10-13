---
id: 003-explain-unobserved-jev-runs
unit: 004-jev-price-promotion
intent: 026-jev-price-comparison
status: complete
priority: must
created: "2026-10-10T01:45:00Z"
assigned_bolt: 089-jev-price-promotion
implemented: true
---

# US-218: Explain Jev runs that produce no price

## User story

As the owner, I want every Jev run to record what it saw and chose in content-free form, so a
failure can be diagnosed without storing Booking.com page content.

## Assigned requirement

FR-15.

## Provenance

Recorded retroactively. The first part was delivered in PR #76 (2026-10-04) outside any story or
bolt, after a live run ended without a price and nothing explained why. This story brings that
work under AI-DLC and extends it.

## Acceptance criteria

- [x] Given any Jev run, when it ends, then entry kind, stage, readiness time, page-read errors,
  per-decision page signature, chosen operations and extraction counts are available (PR #76).
- [x] Given a run with no observation or a timeout, when it ends, then the diagnostic is logged at
  WARNING and kept (PR #76).
- [x] Given the diagnostic, when stored or logged, then it contains no page text, URL or property
  name (asserted by tests, PR #76).
- [ ] Given unpriced rates, when extraction ends, then the count per reason (`none`, `per_night`,
  `original`, `not_total`, `ambiguous`, `unparsed`) is recorded.
- [ ] Given Jev as the only method, when a run ends, then the diagnostic is stored with the run
  ledger and listed by `booksaver comparison report`.
