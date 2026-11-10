---
stage: plan
bolt: 106-jev-judges-room-and-rate-terms
created: 2026-11-10T00:36:30Z
---

# Implementation Plan

- `TrustedPriceQuery.room_type` (optional) carries the booked room to the executor.
- `JevPriceExecutor._extract`: after pricing, if no priced room's name equals the booked one, ask
  `booked_room` twice over the distinct priced room names (with their first card lines); agreement at
  0.8 marks those offers `booked_room`. `ObservedOffer`/`ValidatedObservedOffer` carry the flag; the
  monitor treats it as a room match (confidence 0.9).
- `rate_questions`: add `meal`, `meal_line`, `taxes_line`; `ground_rate` accepts refund, taxes
  and included meals only with a named line at 0.8. `meal_text` carries Jev's meal class;
  `MealPlan.parse` reads it. Remove `classify_meal_text`, `mentions_meals`, `offer_meal_plan` and the
  refund/tax regexes.
- `query_identity_rejection`: exact name equality only when the saved reference is not an https link.
- ADR-064. Unit tests; offline Jev test on captured AIRINN and Park Plaza pages; live staging replay.
