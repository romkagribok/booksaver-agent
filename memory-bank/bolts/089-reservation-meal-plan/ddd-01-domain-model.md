---
stage: model
bolt: 089-reservation-meal-plan
created: "2026-10-10T02:02:11Z"
---

# Reservation meal plan model

- **`MealPlan`** (`domain/meal_plan.py`): `none`, `breakfast`, `half_board`, `full_board`,
  `all_inclusive`, in ascending order of inclusion, plus `unknown`, which is never ranked. Each
  value has a plain-words label for users.
- **`classify_meal_text`**: one pure function for Booking.com meal wording, shared by the
  reservation side now and the offer side in bolt 090. It returns an included value only for
  explicit inclusion wording, `none` only for wording that denies a meal or prices it as an extra,
  and `unknown` otherwise. Meal combinations outside the ranked values are `unknown`.
- **Booked meal plan** is a fact of the reservation, carried as a value plus the bounded verbatim
  line it was read from (at most 200 characters; empty when no line stated it). It lives on
  `ObservedReservation`, `ReservationObservation`, and, value only, on `Booking`.
- **Trust**: only the code-owned confirmation parser produces it. Provider-submitted reservation
  facts have no field for it.
- **Precedence across synchronizations**: a reading stated by a line on the page, then the saved
  value, then a reading taken from a page that stated nothing, then `unknown`.
