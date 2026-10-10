---
intent: 027-meal-plan-equivalence
phase: inception
status: context-defined
created: "2026-10-10T01:49:45Z"
updated: "2026-10-10T01:49:45Z"
---

# System context

The reservation's meal plan enters through account synchronization: the code-owned confirmation
parser reads it from the reservation page text that the grouped inventory reader already captures,
and it travels with the other observed facts into `account_reservations` and the derived `bookings`
projection. Provider-submitted reservation facts cannot set it. `/bookings` renders it from the
stored reservation.

Each price path reports a candidate rate's meal plan with the text it relied on; offer selection in
the domain layer is the single place that compares it with the reservation's. The savings alert and
the paired Jev report read the result. No new external service, secret, or stored page text is
introduced; only the classified value and one bounded verbatim line are stored per reservation.
