---
id: 001-record-reservation-meal-plan
unit: 001-reservation-meal-plan
intent: 027-meal-plan-equivalence
status: in-progress
priority: must
created: "2026-10-10T01:49:45Z"
assigned_bolt: 089-reservation-meal-plan
implemented: false
---

# US-216: Record the reservation's meal plan

As a BookSaver user, I want my reservation's meal plan recorded when my account is
synchronized, so that offers can later be compared like for like.

## Acceptance criteria

- The `Meal Plan` row of the reservation page gives `none` for explicit no-meal wording, the
  included value for explicit inclusion wording, and `unknown` for unrecognized wording.
- Wording that prices a meal as an optional extra is not an inclusion.
- A page with no `Meal Plan` row gives `none` only when the room name and guest row were found
  in the expected order; otherwise `unknown`.
- The value and its verbatim line (at most 200 characters) are stored with the reservation and
  the value reaches the monitored booking.
- Only the code-owned parser can set the meal plan; provider-submitted facts cannot.
- An existing reservation receives its meal plan on the next synchronization. `unknown` never
  replaces a known value, and a value read from a missing row never replaces a stated one.
- A database at schema v19 migrates to v20 with every existing meal plan `unknown`.
