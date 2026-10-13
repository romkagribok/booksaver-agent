---
intent: 027-meal-plan-equivalence
phase: construction
status: complete
created: "2026-10-10T01:38:53Z"
updated: "2026-10-13T13:51:32Z"
---

# Requirements: Meal plan equivalence

## Intent overview

An invited user reported a savings alert for a lower price that was not actually better: the
cheaper offer no longer included the breakfast his reservation includes. BookSaver had no notion
of a meal plan, so a room-only rate for the same room counted as equivalent and, being cheapest,
won. The owner asked that such discrepancies stop.

## Business goals

| Goal | Success metric | Priority |
|------|----------------|----------|
| A reported saving is a like-for-like saving | No alert for an offer with fewer meals than the reservation | Must |
| Users can see what BookSaver read | `/bookings` shows each reservation's recorded meal plan | Must |

## Functional requirements

- **FR-1, meal plan is part of equivalence.** A candidate offer is equivalent only when its meal
  plan is the same as or better than the reservation's. This amends the repository boundary to
  "same property, stay dates, room type, occupancy, and the same or better meal plan".
- **FR-2, meal plan values.** `none`, `breakfast`, `half_board`, `full_board`, `all_inclusive`,
  in that order, plus `unknown`. Wording that names meals but fits none of these (for example
  lunch only) is `unknown`; it is never rounded to a neighbouring value.
- **FR-3, record the reservation's meal plan.** Account synchronization reads the meal plan from
  the reservation page it already loads and stores the value together with the bounded verbatim
  line it was read from. On the layout BookSaver reads, the `Meal Plan` row is authoritative:
  - explicit inclusion wording gives the included value;
  - explicit no-meal wording ("No meal is included in this room rate.") gives `none`;
  - a `Meal Plan` row whose wording is not recognized gives `unknown`;
  - no `Meal Plan` row gives `none` only when the room details section was otherwise recognized
    (room name and guest row found in the expected order); otherwise `unknown`.
  Wording that prices a meal as an optional extra is not an inclusion.
- **FR-4, existing reservations.** Monitored bookings created before this change receive their
  meal plan on the next synchronization. Until then their value is `unknown`. A later
  synchronization may replace `unknown`, and may replace a known value only with a different
  explicitly stated one.
- **FR-5, visible in `/bookings`.** Each listed reservation shows its recorded meal plan in plain
  words, including "meals not confirmed" for `unknown`, so a user can spot a wrong reading.
- **FR-6, read each offer's meal plan.** Every price path that can produce a savings alert
  reports the meal plan of each candidate rate with the verbatim text it relied on, grounded by
  code the same way refundability is. A rate that states nothing about meals is `none`. This is
  the safe direction: it can only exclude an offer, never admit one.
- **FR-7, gate.** Offer selection excludes a candidate whose meal plan ranks below the
  reservation's, or whose meal plan is `unknown` while the reservation includes meals, with its
  own exclusion reason visible in the check trace. When every otherwise-equivalent offer is
  excluded this way, the check reports that no equivalent offer was found; it is not a failure.
- **FR-8, reservation meal plan unknown.** The alert is still sent, states the offer's meal plan,
  and says the reservation's meals could not be confirmed. The owner chose this over sending no
  alert.
- **FR-9, alert wording.** Every savings alert states the reservation's and the offer's meal
  plan. The sentence claiming the offer "matches your stay and room" is only used with that
  statement.
- **FR-10, every price method.** The rule applies to whichever price method is authoritative and
  to a paired comparison arm, so results stay like-for-like. A method that cannot ground an
  offer's meal plan reports `unknown`.
- **FR-11, verification.** Parser and gate tests use the real examples supplied by the owner plus
  synthetic variants for each value, the optional-extra wording, the missing row, and the
  unrecognized row. Offer-side wording is qualified against saved real property pages before the
  gate is enabled in production.

## Non-functional requirements

| Area | Requirement |
|------|-------------|
| Trust | Only code-owned readers set a reservation's meal plan; provider output cannot. |
| Privacy | One bounded line (at most 200 characters) of Booking.com rate wording is stored per reservation; no page text, and no unrecognized free text from the page. |
| Compatibility | The migration is additive; the previous image keeps working on the migrated database. |
| Cost | Recording adds no model call, browser action or page load to a synchronization. |

## Constraints

Booking.com hotels only, refundable offers only, no autonomous booking action, no rebooking
workflow. Per-user boundaries are unchanged.

## Assumptions

| Assumption | Risk if invalid | Mitigation |
|------------|-----------------|------------|
| The desktop reservation layout states the meal plan in a `Meal Plan` row | A real inclusion is read as `none` | Unlabelled wording in the room section is also read; `/bookings` shows the reading; the gate ships only after production readings are reviewed |
| The desktop wording for an included breakfast resembles the app's "Breakfast included" | The owner's father's reservation reads `unknown` | The verbatim line is stored, so the wording can be added from the first production reading |

## Open questions

| Question | Owner | Resolution |
|----------|-------|------------|
| What happens when the reservation's meal plan is unknown? | Owner | Resolved 2026-10-10T01:49:45Z: send the alert with a caveat (FR-8) |
| Are the bolt's stage checkpoints waived for bolt 090? | Owner | Resolved 2026-10-10T08:07:38Z: waived after the fact, on a review of the stage summary |
| Should the decisions be recorded as ADR-057? | Owner | Resolved 2026-10-10T08:07:38Z: accepted |

## Delivery order

Recording and display (FR-2 to FR-5, bolt 090) ship first without the gate. The gate (FR-1 and
FR-6 to FR-10, bolt 091) follows once production reservations confirm the readings.

## Approval

The owner approved recording the meal plan and decided that a reservation page stating no meal
plan means no meals, then on 2026-10-10T01:49:45Z approved these requirements, chose the caveated alert, and said:
"proceed to implement, merge and redeploy to vps if everything is settled and wait for bugbot
review if it is available".

## Investigation evidence

- `src/booksaver/domain/offer.py`: `select_offer` excludes on refundability, room, match
  confidence, and currency, then takes the cheapest survivor. Meals are not considered.
- `src/booksaver/domain/models.py`, `src/booksaver/domain/account_sync.py`: neither `Booking` nor
  `ReservationObservation` carried a meal plan.
- `src/booksaver/infrastructure/browser/inventory_confirmation_facts.py`: `_room_fact` read the
  room name under "Your room details" and nothing else in that section.
- `src/booksaver/infrastructure/browser/grouped_inventory_reader.py`: the snapshot already carries
  up to 60,000 characters of the reservation page's visible text; that text is not persisted.
- `src/booksaver/infrastructure/persistence/sqlite_store.py`: an existing reservation row keeps
  its stored facts in preference to newly observed ones, so FR-4 needs an explicit rule.
- No price path asks what a rate includes; the alert says the offer "is confirmed refundable and
  matches your stay and room".
- Owner example, desktop layout (the one synchronization reads): rows `Guest name`,
  `Max capacity`, `Meal Plan` = "No meal is included in this room rate.", `Smoking preference`,
  `Facilities`.
- Owner example, Booking.com app layout: a standalone "Breakfast included" line. Synchronization
  does not read this layout; the desktop wording for an included breakfast is still to be observed.

## Out of scope

Other rate conditions (payment timing, cancellation deadline).

## Amendment 2026-10-10T07:49:45Z: numbering and FR-10

PR #78 (intent 026) merged first and took schema v20, bolt 089, US-216 to US-219 and ADR-056.
This intent was renumbered before merging: schema v21, bolts 090 and 091, stories US-220 to
US-225. FR-10 originally named only the paired Jev arm; ADR-056 has since made Jev selectable as
the authoritative price method, so the requirement now covers whichever method is authoritative.
No scope was added or dropped.

## Amendment 2026-10-13T13:51:32Z: what was not built or not evidenced

Recorded when the owner closed the intent. These are descoped or unproven, not delivered:

- **FR-11, qualification against saved real property pages before production enablement**: not
  done. No real rate table was available before release. It was replaced by a production
  read-back after release: on three properties every accepted rate was classified `breakfast` or
  `none`, none `unknown`. That shows the classifier produced plausible values, not that each
  matches its page; the wording itself is not recorded.
- **FR-10 on the model price paths**: built and unit-tested, never run in production with the
  gate. Production switched to Jev as the only price method 13 minutes after this release, so
  Browser Use and the legacy extraction are unproven with model-copied meal wording. Stagehand
  was not extended and reports `unknown`.
- **FR-9, alert wording**: built and tested; no production alert has been sent since the release
  because no check found a saving, so the new wording has not been seen live.
- **Design items cut before coding** (never requirements): storing the offer's meal plan, a
  `/savings` line, `/checknow` success wording and the paired-report line.
- **Monitoring**: the owner asked for 24 hours and closed the intent after about 15, on two of the
  three scheduled checks of the reservation with breakfast.
