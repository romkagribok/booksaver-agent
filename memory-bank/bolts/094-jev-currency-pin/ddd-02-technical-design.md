---
unit: 002-jev-currency-pin
bolt: 094-jev-currency-pin
stage: design
status: complete
created: 2026-11-03T00:52:47Z
updated: 2026-11-03T00:52:47Z
---

# Technical Design - Jev Currency Pin

After the entry navigation and its invariant, `execute()` reads the current URL. For a property
entry, `_url_with_currency` returns the URL with `selected_currency` set, or None when already
correct or unreadable. On a URL it records one action, adds a `PIN_CURRENCY` step, navigates once and
re-checks the invariant, ending as `currency_invariant` on failure. The pinned URL becomes the entry
URL passed to `_navigate_until_offers`, so an error-page reload keeps it. Search entries and the
dormant Claude methods are unchanged.

Adding `changed_currency=1` to the first URL was tested live and did not help, so it is not used.

No ADR: this follows Booking.com's existing URL parameter and changes no decision.

## Test Plan

Helper cases, one re-open when dropped, none when kept, invariant failure, pinned entry URL, and one
Jev check on staging with the owner's session.
