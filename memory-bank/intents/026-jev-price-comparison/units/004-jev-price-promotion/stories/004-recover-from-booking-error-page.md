---
id: 004-recover-from-booking-error-page
unit: 004-jev-price-promotion
intent: 026-jev-price-comparison
status: complete
priority: must
created: "2026-10-10T01:45:00Z"
assigned_bolt: 089-jev-price-promotion
implemented: true
---

# US-219: Recover from Booking.com's transient error page

## User story

As a booking owner, I want a price check to reload when Booking.com shows its error page, so a
transient site error does not fail my check.

## Assigned requirement

FR-16.

## Background

Three live Jev runs ended with no price after exactly six navigation decisions. The two recorded
after diagnostics existed (2026-10-09T16:08Z and 16:10Z) show the same page at every step:
property URL, no rooms, one heading, 221 characters of text, the error-page marker, no guarded
controls; Jev chose WAIT six times at 0.52 to 0.69 confidence. The first (2026-10-03T22:11Z) has
the same call count and prompt size but was not recorded.

## Acceptance criteria

- [ ] Given the error page and no room list, when navigation starts, then the trusted entry URL is
  reloaded (at most twice, with a short pause) before Jev is asked anything.
- [ ] Given a reload, when it completes, then the single-target and allowed-destination
  invariants are rechecked and each reload counts toward the browser-action cap.
- [ ] Given the error page persists, when reloads are exhausted, then Jev decides as before and
  the diagnostic shows the reloads.
- [ ] Given a page with no rooms that is not the error page, when navigating, then it is not
  reloaded.

## Out of scope

Retrying whole checks; treating bot-wall or sign-in pages as errors to reload.
