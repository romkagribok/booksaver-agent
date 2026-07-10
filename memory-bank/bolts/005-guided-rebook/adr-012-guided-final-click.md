---
unit: 004-guided-rebook
bolt: 005-guided-rebook
id: ADR-012
title: Guided final click — MVP does not automate the destructive button press
status: accepted
updated: 2026-07-05T00:00:00Z
---

# ADR-012: Guided final click

## Context

US-011 requires a mandatory local confirmation before cancel or purchase. After the
user confirms, the automation *could* programmatically click Booking.com's final
cancel/purchase buttons, or it could navigate to the correct page and let the user
perform the final click themselves.

## Decision

MVP performs a **guided final click**: after each explicit confirmation, the browser
opens the correct page (cancellation page / rebook search for the same property, dates,
and room), and the human performs Booking.com's own final action. The state machine,
confirmation gates, and audit trail are fully automated; the irreversible click is not.

## Rationale

- **Safety-first product constraint**: "no autonomous cancel or purchase" is the MVP's
  core trust promise. A programmatic click on a money-moving button, driven by selectors
  against a third-party page we cannot regression-test, is exactly the failure mode the
  product exists to avoid. A mis-click cancels a real reservation.
- **Acceptance criteria remain satisfied**: automation "prepares the rebook path",
  stops at gates, requires per-action confirmation, and proceeds "only for that single
  approved action" — navigation-then-handoff is a valid (and conservative) reading of
  "proceed".
- Booking.com's cancel/purchase flows include their own confirmations, price re-checks,
  and payment steps; automating through those adds large surface area for silent breakage
  with near-zero user benefit over an opened, correct page.

## Consequences

- The user makes 1–2 clicks per rebook that a fully automated flow would make for them.
  Acceptable at MVP scale (rebooks are rare events).
- `execute_cancel` / `execute_book` steps are navigation + handoff; a future bolt can
  swap in full automation behind the same state machine if trust and testability improve.
- The audit trail records `action_executed` when the page is opened and handed off; the
  human's final click on Booking.com is outside the trail (documented in rebook output).
