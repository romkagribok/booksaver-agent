---
id: 002-tolerate-read-only-destinations-and-diagnose-rejections
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-08-27T23:13:41.000Z
assigned_bolt: 056-agentic-inventory-executor
implemented: true
---

# Story: Tolerate Read-Only Destinations and Diagnose Rejections

## User Story

**As a** BookSaver deployment owner
**I want** agentic inventory to tolerate benign Booking.com route and query churn while explaining
every destination rejection safely
**So that** the browser reaches semantic perception without weakening account or transaction guards

## Acceptance Criteria

- [x] Fixed code-owned inventory navigation may follow HTTPS redirects within the Booking.com domain
  boundary without requiring an exact known path or a fixed set of benign provider query keys.
- [x] Destination policy distinguishes `deny`, `observe_only`, and `interact`: unknown non-mutating
  Booking.com pages may be perceived, while interaction still requires task-specific, code-verifiable
  read-only evidence.
- [x] Authentication, MFA, captcha, bot-wall, account settings, modification, cancellation,
  reservation, checkout, payment, purchase, download, popup, non-Booking, non-HTTPS, user-info, and
  nonstandard-port destinations remain terminal or prohibited.
- [x] Provider descriptions never authorize an action; only inspected browser metadata and
  code-owned task context may admit replay.
- [x] Rejected destinations emit a bounded diagnostic containing only a destination class,
  sanitized path template, sorted query-key names, and rejection phase/reason.
- [x] Raw URLs, query values, fragments, reservation identifiers, page content, screenshots,
  selectors, cookies, credentials, and model reasoning never enter logs or persisted metrics.
- [x] The live `non_allowlisted_destination` failure shape is covered by regression tests proving
  that benign Booking.com redirects reach semantic extraction and unsafe routes still fail closed.

## Dependencies

- US-153; ADR-034, ADR-036, ADR-037, and ADR-039.

## Out of Scope

- Non-Booking.com egress, credential entry, autonomous account mutation, raw-URL retention, selector
  repair, or changing positive-only reconciliation.
