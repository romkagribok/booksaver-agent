---
stage: implement
bolt: 106-jev-judges-room-and-rate-terms
created: 2026-11-10T01:03:30Z
---

# Implementation Walkthrough

- `JevPriceExecutor._booked_room` asks `booked_room` twice over the distinct priced room names (each
  with up to six short card lines) when none equals the booked name ignoring case and spacing;
  agreement at 0.8 marks that room's offers `booked_room`. The diagnostic records `booked_room=y|n`.
- `rate_questions` adds `taxes_line` (room card notes and rate lines), `meal` and `meal_line`;
  `ground_rate` uses `_sure` (0.8) and `_names_line`; `meal_text` now carries Jev's meal class and
  `MealPlan.parse` reads it. The meal word lists and the refund/tax regexes are deleted.
- The meal hint says a meal only named, without saying it is included, is not included: the live
  wording check read a bare "Breakfast" line as included before it.
- `query_identity_rejection`: exact name only for non-https references.
- Rebased on #108 (per-user Jev cap), which ships in the same image.
