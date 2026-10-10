---
adr: ADR-057
bolt: 090-reservation-meal-plan
created: "2026-10-10T07:49:45Z"
status: accepted
accepted: "2026-10-10T08:07:38Z"
---

# ADR-057: Meal plan is part of offer equivalence and is read by code

Drafted from the requirements the owner approved on 2026-10-10T01:49:45Z and accepted by the
owner on 2026-10-10T08:07:38Z, after the implementation of bolt 090.

## Context

A user was alerted to a cheaper offer that dropped the breakfast his reservation includes.
Equivalence covered property, stay dates, room type and occupancy only. Booking.com lists the same
room at several rates, so the room-only rate is systematically the cheapest candidate.

## Decision

1. Offer equivalence requires the same or a better meal plan. Values are ranked `none`,
   `breakfast`, `half_board`, `full_board`, `all_inclusive`; `unknown` is never ranked and wording
   is never rounded to a value.
2. A reservation's meal plan is set only by the code-owned confirmation parser, from the room
   details section of the reservation page. It is attached after the typed provider mapper, so
   provider output cannot supply it.
3. A reservation page that states nothing about meals means no meals, but only when the room
   name and guest row were read; otherwise the meal plan is `unknown`.
4. An offer that states nothing about meals has none. An offer with an `unknown` meal plan is
   excluded when the reservation includes meals.
5. When the reservation's meal plan is `unknown`, the alert is still sent with a caveat.

Points 1, 4 and 5 take effect with bolt 091; points 2 and 3 with bolt 090.

## Rationale

### Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| Treat a silent reservation page as `unknown` | Never a wrong `none` | Every room-only reservation on a layout without a row would carry a caveat forever | Owner decision; the guard limits the risk |
| Let the model-assisted paths report the meal plan | Covers accounts the grouped reader cannot read | Provider output would decide what counts as equivalent | Provider output is untrusted |
| Send no alert while the reservation's meal plan is unknown | Fails closed | Existing bookings go silent until their next successful reading | Owner chose the caveated alert |
| Require an identical meal plan | Simplest rule | Hides a cheaper offer that includes more | Same or better is still a real saving |

## Consequences

### Positive

- A reported saving is like for like on meals.
- Users see the recorded meal plan in `/bookings` and both meal plans in an alert.

### Negative

- Point 3 is an intentional exception to the "no silent default" principle of ADR-014.
- The meal plan bypasses the typed mapper that ADR-048 routes confirmation facts through.
- Reservations read only by a model-assisted path stay `unknown`.

### Risks

- A layout that states an inclusion in wording the parser does not recognize reads as `unknown`,
  or as `none` if it is outside the room section. Mitigation: the stored line, the `/bookings`
  line, and releasing the gate only after production readings are reviewed.

## Related

- **Stories**: US-220 to US-225
- **Standards**: the equivalence boundary in `AGENTS.md` is amended with bolt 091
- **Previous ADRs**: ADR-014, ADR-027, ADR-039, ADR-048, ADR-056
