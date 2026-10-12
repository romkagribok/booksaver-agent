---
unit: 013-confirmation-booked-total
intent: 023-replaceable-agentic-browser-executor
phase: construction
status: complete
unit_type: backend
default_bolt_type: ddd-construction-bolt
created: "2026-10-10T01:59:26Z"
---

# Confirmation Booked Total

## Scope and requirements

FR-34 / US-226: Record the booked total in the currency the confirmation page prints and read the
refund schedule layout. FR-35 / US-227: Let a reader-reconciled total replace a different saved
total and baseline. FR-36 / US-228: Qualify against the affected caller's real page and identify
unsupported layouts without exposing content.

The owner requested the fix directly and waived per-step approval for this task, with every step
recorded. The change is local reading and reconciliation; it never changes a Booking.com
reservation, converts currencies or logs page content.

## Domain and boundaries

The booked total is the all-in amount the guest owes, stated once on the confirmation page in one
currency. It is the baseline every later price check compares against, in that same currency. A
total is page-verified only when the code-owned reader reconciled it from the page's own component
rows; provider-submitted totals are never page-verified. A saved total is replaced only by a
page-verified total for the same caller and confirmation identity.

Use the existing grouped reader, validator, coordinator lease, SQLite transaction and eligibility
policy. No new service, browser route, dependency or schema migration.
Dependencies: completed Units004, 011, 012.

## Story summary

Three Must stories, US226–228, assigned only to Bolt092.

## Exit criteria

Construction requires implemented stories, positive and negative regressions for currency,
refund schedule and saved-total replacement, the quality and AI-DLC gates, and documented
affected-caller acceptance on the real confirmation page. The dollar layout was derived from a
cropped screenshot, so unit tests alone do not establish acceptance.
Operations separately requires current-head Bugbot, exact-image Development and isolated Staging,
backup and rollback, authorized promotion and production state checks.
