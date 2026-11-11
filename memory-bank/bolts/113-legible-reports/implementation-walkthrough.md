---
stage: implement
bolt: 113-legible-reports
created: 2026-11-11T00:26:06Z
---

# Implementation Walkthrough: legible-reports

## Summary

- **`check_refund`:** a dated free-cancellation deadline that has ended everywhere returns
  `explicit_nonrefundable` with "Free cancellation ended on <d Mon yyyy>." "Ended everywhere"
  means a full day plus the 14-hour timezone margin after the date. A date that may still be
  running somewhere stays unread. "Within" windows and deadlines after check-in are unchanged.
- **New `infrastructure/telegram/plain_text.py`:** `day`, `stay`, `moment`, `money`,
  `versus_paid`, `failure_text` (one sentence per failure code, with a fallback) and
  `checked_as`.
- **`/bookings`:** readable stay, a "Free cancellation until <date>" line, and the reasons "no
  free cancellation" and "cancellation terms unknown".
- **`/savings`:** the hotel and stay, price paid and price found, the saving, and when it was
  found.
- **`/checks`:** a header with the hotel, stay and price paid, then each check in plain words.
  The not-found reply is still the same for missing and foreign bookings.
- **`/checknow`:** the same wording, plus a note when the saving is under the 5-unit alert
  minimum.
- **Alert:** "Checked as: signed in to your Booking.com account", and "Genius prices were shown"
  when they were.

## Deviations

None. No schema, config or Jev question change.
