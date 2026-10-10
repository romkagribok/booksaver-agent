---
intent: 027-meal-plan-equivalence
phase: inception
status: construction
created: "2026-10-10T01:38:53Z"
updated: "2026-10-10T02:02:11Z"
---

# Meal plan equivalence

## Request and checkpoint

An invited user reported a savings alert for a lower price that was not actually better: the
cheaper offer no longer included the breakfast his reservation includes. The owner asked that such
discrepancies stop, approved recording each reservation's meal plan, and decided that a
reservation whose page states no meal plan is treated as having no meals. The owner approved these
requirements, chose the caveated alert for an unknown reservation meal plan, and authorized
implementation through merge and redeploy, waiting for Bugbot when it is available. Approval
recorded 2026-10-10T01:49:45Z.

## Approved requirements

1. **Meal plan is part of equivalence.** A candidate offer is equivalent only when its meal plan is
   the same as or better than the reservation's. This amends the repository boundary to "same
   property, stay dates, room type, occupancy, and the same or better meal plan" and is recorded as
   a new ADR.
2. **Meal plan values.** `none`, `breakfast`, `half_board`, `full_board`, `all_inclusive`, in that
   order, plus `unknown`. Wording that names meals but fits none of these (for example lunch only)
   is `unknown`; it is never rounded to a neighbouring value.
3. **Record the reservation's meal plan.** Account synchronization reads the meal plan from the
   reservation page it already loads and stores the value together with the bounded verbatim line
   it was read from. On the layout BookSaver reads, the `Meal Plan` row is authoritative:
   - explicit inclusion wording gives the included value;
   - explicit no-meal wording ("No meal is included in this room rate.") gives `none`;
   - a `Meal Plan` row whose wording is not recognized gives `unknown`;
   - no `Meal Plan` row gives `none` only when the room details section was otherwise recognized
     (room name and guest row found in the expected order); otherwise `unknown`.
   Wording that prices a meal as an optional extra is not an inclusion.
4. **Existing reservations.** Monitored bookings created before this change receive their meal
   plan on the next synchronization. Until then their value is `unknown`. A later synchronization
   may replace `unknown`, and may replace a known value only with a different explicitly stated one.
5. **Visible in `/bookings`.** Each listed reservation shows its recorded meal plan in plain words,
   including "meals not confirmed" for `unknown`, so a user can spot a wrong reading.
6. **Read each offer's meal plan.** Every price path that can produce a savings alert reports the
   meal plan of each candidate rate with the verbatim text it relied on, grounded by code the same
   way refundability is. A rate that states nothing about meals is `none`. This is the safe
   direction: it can only exclude an offer, never admit one.
7. **Gate.** Offer selection excludes a candidate whose meal plan ranks below the reservation's,
   or whose meal plan is `unknown` while the reservation includes meals, with its own exclusion
   reason visible in the check trace. When every otherwise-equivalent offer is excluded this way,
   the check reports that no equivalent offer was found; it is not a failure of the check.
8. **Reservation meal plan unknown.** The alert is still sent, states the offer's meal plan, and
   says the reservation's meals could not be confirmed. The owner chose this over sending no alert.
9. **Alert wording.** Every savings alert states the reservation's and the offer's meal plan. The
   sentence claiming the offer "matches your stay and room" is only used with that statement.
10. **Paired comparison.** The Jev arm applies the same rule so the paired experiment stays
    like-for-like. If it cannot ground an offer's meal plan it reports `unknown`.
11. **Verification.** Parser and gate tests use the two real examples supplied by the owner plus
    synthetic variants for each value, the optional-extra wording, the missing row, and the
    unrecognized row. Offer-side wording is qualified against saved real property pages before the
    gate is enabled in production.

## Delivery order

Recording and display (requirements 3 to 5) ship first without the gate. The gate (6 to 10)
follows once production reservations confirm the readings.

## Investigation evidence

- `src/booksaver/domain/offer.py`: `select_offer` excludes on refundability, room, match
  confidence, and currency, then takes the cheapest survivor. Meals are not considered.
- `src/booksaver/domain/models.py`, `src/booksaver/domain/account_sync.py`: neither `Booking` nor
  `ReservationObservation` carries a meal plan.
- `src/booksaver/infrastructure/browser/inventory_confirmation_facts.py`: `_room_fact` reads the
  room name under "Your room details" and nothing else in that section.
- `src/booksaver/infrastructure/browser/grouped_inventory_reader.py`: the snapshot already carries
  up to 60,000 characters of the reservation page's visible text; that text is not persisted.
- `src/booksaver/infrastructure/persistence/sqlite_store.py`: an existing reservation row keeps
  its stored facts in preference to newly observed ones, so the backfill in requirement 4 needs
  an explicit rule.
- `src/booksaver/domain/browser_executor.py`, `browser_use_price_executor.py`,
  `jev_price_executor.py`, `anthropic_adapter.py`, `monitor/room_table.py`: no price path asks
  what a rate includes.
- `src/booksaver/application/savings_pipeline.py`: the alert says the offer "is confirmed
  refundable and matches your stay and room".
- Owner example, desktop layout (the one synchronization reads): rows `Guest name`,
  `Max capacity`, `Meal Plan` = "No meal is included in this room rate.", `Smoking preference`,
  `Facilities`.
- Owner example, Booking.com app layout: a standalone "Breakfast included" line. Synchronization
  does not read this layout; the desktop wording for an included breakfast is still to be observed.

## Unchanged scope

Booking.com hotels only, refundable offers only, no autonomous booking action, no rebooking
workflow. Per-user boundaries are unchanged. Other rate conditions (payment timing, cancellation
deadline) are not part of this intent.
