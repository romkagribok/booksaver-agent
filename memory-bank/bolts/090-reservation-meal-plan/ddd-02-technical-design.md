---
unit: 001-reservation-meal-plan
bolt: 090-reservation-meal-plan
stage: design
status: complete
created: "2026-10-10T02:02:11Z"
updated: "2026-10-10T07:49:45Z"
---

# Technical Design - Reservation meal plan

Written after the code it describes (see the bolt's "Stage checkpoints").

## Architecture Pattern

Unchanged: the existing layered, single-process architecture with explicit domain types. The meal
plan follows the path the other reservation facts already take.

## Layer Structure

```text
Presentation     /bookings adds one "Meals:" line per reservation (commands_readonly)
Application      duplicate merge and conversion to ReservationObservation (inventory_executor)
Domain           MealPlan, classify_meal_text (meal_plan); fields on ObservedReservation,
                 ReservationObservation and Booking
Infrastructure   confirmation parser (_meal_facts); hand-off in the Browser Use inventory
                 executor (_with_parsed_meal_plans); SQLite store and schema v21
```

## API Design

No HTTP API. The Telegram `/bookings` reply gains one line per reservation, `Meals: <label>`;
`unknown` is shown as "meals not confirmed". The stored wording is not shown.

## Data Persistence

| Table | Columns | Relationships |
|-------|---------|---------------|
| `account_reservations` | `meal_plan TEXT`, `meal_plan_text TEXT NOT NULL DEFAULT ''` | unchanged |
| `bookings` | `meal_plan TEXT` | unchanged |

Schema v21, added by `_migrate_v21` (add column if missing); `NULL` means not read yet.
`_meal_plan_to_store` applies the reading precedence on every extraction path. The booking's meal
plan is written outside the projection's change detection, so recording it does not delete a
saved opportunity. The migration is additive, so the previous image keeps working on a migrated
database.

## Parser

`inventory_confirmation_facts._meal_facts` works only inside the room details section (from
"Your room details" to the cancellation or price heading, at most 60 lines).

1. A labelled `Meal Plan` row is authoritative, with the value inline or on the next line.
2. Without one, standalone meal wording in the section is classified; an inclusion stands even
   beside a priced extra.
3. A section with a guest row and no meal wording gives `none` with no text.
4. No recognized room, or no guest row, gives `unknown`.

The value of a facilities row describes the room, not the rate, and is never meal evidence.
Unlabelled wording that is not recognized may be the guest's own text and is not kept.

## Security Design

| Concern | Approach |
|---------|----------|
| Provider output is untrusted | The provider payload models and `_OPTIONAL_FACT_FIELDS` are unchanged, so model-assisted paths cannot set a meal plan. Parsed payloads are matched to mapped reservations by confirmation number after the established mapper has run. |
| Per-user boundaries | The value is stored on the caller's own reservation row and shown only in the caller's `/bookings`. |
| Stored content | One bounded line of Booking.com rate wording; no page text; no unrecognized free text. |

## NFR Implementation

| Requirement | Design Approach |
|-------------|-----------------|
| Cost | No model call, browser action or page load is added; the parser reads text already captured. |
| Reliability | Disagreeing duplicate readings downgrade to `unknown` instead of rejecting the reservation. |

## Error Handling

| Error Type | Response |
|------------|----------|
| Unrecognized wording | `unknown`, wording kept only for a labelled row |
| A confirmation parsed twice with different readings | `unknown` |
| Unrecognized stored value | read as `unknown` |

## External Dependencies

None added.

## Prior decisions considered

- ADR-014 (no silent default for occupancy): the silent `none` is an intentional, owner-decided
  exception, guarded by the recognized room section. Drafted in ADR-057.
- ADR-048 (bounded grouped inventory details): confirmation facts pass the typed mapper. The meal
  plan is attached after that mapper so provider output cannot supply it. Drafted in ADR-057.
- ADR-027 and ADR-039: account inventory stays authoritative and positive-only; unchanged.
- ADR-001: additive SQLite migration; followed.

## Not changed

Offer selection, alerts, every price method, and the paired comparison.
