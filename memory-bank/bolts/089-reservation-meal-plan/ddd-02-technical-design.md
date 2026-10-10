---
stage: design
bolt: 089-reservation-meal-plan
created: "2026-10-10T02:02:11Z"
---

# Technical design and decision

- **Parser** (`inventory_confirmation_facts._meal_facts`): works only inside the room details
  section (from "Your room details" to the cancellation or price heading, at most 60 lines). A
  labelled `Meal Plan` row is authoritative, with the value inline or on the next line. Without
  one, standalone meal wording in the section is classified; an inclusion stands even beside a
  priced extra. A section with a guest row and no meal wording gives `none` with no text. No
  recognized room, or no guest row, gives `unknown`.
  Unlabelled wording that is not recognized may be the guest's own text and is not kept.
- **Hand-off** (`browser_use_inventory_executor._with_parsed_meal_plans`): the grouped reader's
  parsed payloads are matched to mapped reservations by confirmation number after the established
  mapper has run. The provider payload models and `_OPTIONAL_FACT_FIELDS` are unchanged, so the
  model-assisted paths cannot set a meal plan. A confirmation parsed twice with different readings
  stays `unknown`.
- **Duplicate merge** (`application/inventory_executor._merge_compatible`): disagreeing meal
  readings downgrade to `unknown` instead of rejecting the reservation.
- **Storage** (schema v20): `account_reservations.meal_plan`, `account_reservations.meal_plan_text`
  and `bookings.meal_plan`, added by `_migrate_v20`; `NULL` means not read yet.
  `_meal_plan_to_store` applies the precedence from the domain model on every extraction path.
  The booking's meal plan is written outside the projection's change detection, so recording it
  does not delete a saved opportunity.
- **Display**: `/bookings` adds one `Meals:` line per reservation from the label.
- **ADR analysis**: no new decision in this bolt. The reading rule is approved requirement 3 of
  intent 027; the equivalence decision and the amended repository boundary are recorded with
  bolt 090, which is where behaviour toward offers changes.
- **Not changed**: offer selection, alerts, every price path, and the paired comparison.
