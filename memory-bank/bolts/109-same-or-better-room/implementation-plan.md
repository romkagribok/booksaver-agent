---
stage: plan
bolt: 109-same-or-better-room
created: 2026-11-10T01:15:25Z
---

# Implementation Plan

- `JevPriceExecutor._booked_room` becomes `_room_matches`: rooms carrying the booked name are
  "same" by code; every other priced room gets one question (same / better / neither) in one call,
  with the booked room and guests in the state; asked twice, agreement at 0.8.
- `ObservedOffer.booked_room`/`ValidatedObservedOffer.booked_room` become `room_match`
  ("same" | "better" | None); the monitor counts both as a room match.
- `OfferCandidate.room_match` and `CheckResult.offer_room`/`offer_room_better` carry the chosen
  differently named room to `render_alert`, which adds "Room (offer)" and adjusts the match sentence.
- Unit tests; staged replay of AIRINN, Park Plaza and the other monitored bookings.
