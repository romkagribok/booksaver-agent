---
unit: 002-meal-aware-offers
bolt: 091-meal-aware-offers
stage: design
status: complete
created: "2026-10-10T08:22:31Z"
updated: "2026-10-10T08:22:31Z"
---

# Technical Design - Meal-aware offers

Written before any code for this bolt and without reading source files in this stage. Module and
function names come from the investigation recorded in the requirements, from bolt 090, and from
bolt 089's design; each is confirmed against the code at the start of Stage 4, and any difference
is recorded as a plan departure rather than silently adapted.

## Architecture Pattern

Unchanged: the layered single-process daemon, with every price method behind one provider-neutral
port returning untrusted typed evidence, and BookSaver alone deciding equivalence (ADR-043,
ADR-056). The meal plan follows the path refundability already takes: evidence from the method,
judgement in the domain.

## Layer Structure

```text
Presentation     savings alert, /savings, /checknow result and the paired report state meal plans
Application      savings pipeline builds the meal statement; opportunity carries both meal plans
Domain           ObservedOffer.meal_text; OfferCandidate.meal_plan; select_offer meal rule;
                 CheckResult.offer_meal_plan; SavingsOpportunity meal plans
Infrastructure   each price method fills meal_text; SQLite schema v22; trace records per candidate
```

## How each price method supplies the meal wording

| Price method | Source of the wording | Model involvement | Cost |
|--------------|-----------------------|-------------------|------|
| Jev (authoritative after ADR-056 phase 2; comparison arm today) | The lines of the rate row that the code-owned page snapshot already holds. Code selects the lines that mention meals and classifies them. Room-card lines (facilities) are not used. | None. Jev is not asked about meals. | No extra call |
| Browser Use and Stagehand (LLM price path) | One new required field per offer in the existing submission: the rate's visible meal wording copied verbatim, `none` when the rate shows nothing about meals, `unknown` when it cannot tell. | The model copies text; BookSaver classifies it. | Same single submission |
| Legacy scripted path | The existing offer-extraction prompt gains the same field. The DOM-only parser reports `none` when the room block shows no meal wording and `unknown` when it shows any, because it cannot tie a line to one rate; when the reservation includes meals a DOM-only match is therefore not confident and extraction falls through to the model, as it already does for other uncertainty. | As today | One extraction call for reservations with meals |

Classification rules for an offer's wording: the same `classify_meal_text` as bolt 090; an
inclusion stands beside a priced extra on other lines; the `none` marker or no meal wording gives
`none`; `unknown`, an empty value, or wording that does not classify gives `unknown`. The wording
kept with a candidate is bounded to 200 characters.

## API Design

No HTTP API. User-visible text changes:

| Surface | Change |
|---------|--------|
| Savings alert | Adds `Meals (your booking): <label>` and `Meals (this offer): <label>`. The closing sentence becomes "The cheaper offer is confirmed refundable and matches your stay, room and meal plan." When the reservation's meal plan is unknown it becomes "The cheaper offer is confirmed refundable and matches your stay and room. We could not confirm which meals your booking includes, so compare meals before you rebook." |
| `/savings` | Each opportunity shows the offer's meal plan; older rows show "meals not recorded". |
| `/checknow` result and scheduled reports | A success states the offer's meal plan. A check whose remaining offers were all excluded on meals says "No refundable offer for your room includes your booking's meals (<label>)." |
| Paired comparison report | Each arm row states the offer's meal plan. |

## Data Persistence

| Table | Columns | Relationships |
|-------|---------|---------------|
| `check_history` | `offer_meal_plan TEXT` | unchanged |
| `savings_opportunities` | `offer_meal_plan TEXT`, `booked_meal_plan TEXT` | unchanged |

Schema v22, additive; `NULL` on rows written before this release. The check trace records, per
candidate, the classified meal plan, its bounded wording and any meal exclusion.

**Migration safety.** Release 1 showed that the daemon opens the database from several threads at
start, so two connections can run the same migration (release record
`d19f7b5-reservation-meal-plan.md`). Schema application is serialized: the version check and the
migrations run inside one `BEGIN IMMEDIATE` transaction that re-reads the version after taking the
lock, and a column that already exists is not an error. This covers v22 and repairs v21 for
installations that have not migrated yet.

## Selection and outcome

- `select_offer` applies the meal rule from the domain model after refundability, room and match
  confidence, and before currency, so an offer set aside for its rendered currency is one that
  also satisfies meals.
- A reservation whose meal plan is `unknown` or `none` adds no exclusion, so behaviour for those
  bookings is unchanged apart from the wording of the alert.
- When every remaining candidate is excluded on meals, the check ends as the existing
  no-equivalent-offer observation with the meal counts in its detail. Intent 018 already makes
  that observation conclusive: it clears the booking's current opportunity. No incident, terminal
  diagnosis or retry is raised for it.
- A saved opportunity validated before this release is not rewritten. The next conclusive check
  replaces or clears it, which is the re-evaluation US-224 asks for.

## Security Design

| Concern | Approach |
|---------|----------|
| Provider output is untrusted | Price methods supply wording only. The meal plan value is always computed by BookSaver. |
| Model-copied wording (Browser Use, Stagehand, legacy extraction) | Same trust level as the cancellation wording these paths already copy. A missing or unclear value becomes `unknown` or `none`, which can only exclude an offer. A fabricated inclusion could admit one; this residual risk is stated in ADR-057's addendum and does not exist on the Jev path, where the lines come from the code-owned snapshot. |
| Stored content | At most 200 characters of rate wording per candidate in the local check trace. |
| Per-user boundaries | Unchanged; meal plans appear only in the booking owner's own messages. |

## NFR Implementation

| Requirement | Design Approach |
|-------------|-----------------|
| Cost | No extra model call on the Jev or Browser Use path. |
| Fail closed | Every uncertain reading resolves to `unknown`, which excludes the offer when the reservation includes meals. |
| Compatibility | Additive schema; the previous image runs on the migrated database. Rollback is the previous image tag. |

## Error Handling

| Error Type | Response |
|------------|----------|
| Offer wording missing, empty or unclassifiable | offer meal plan `unknown` |
| All remaining offers excluded on meals | conclusive no-equivalent-offer observation |
| Reservation meal plan `unknown` | no meal exclusion; alert carries the caveat |
| Stored meal plan value not recognized | read as `unknown` |

## External Dependencies

None added.

## Verification plan (FR-11)

- Unit: the meal rule table, exclusion order, currency interaction, each price method's mapping
  from wording to meal plan, alert and report wording for confirmed and unknown reservations.
- Integration: schema v22 on a v21 database, including two connections migrating at once;
  opportunity and history round trips.
- Real wording: no saved production trace contains rate wording (230 traces searched, none
  mentions meals), so the repository holds no real rate table. The owner is asked for one real
  property-page rate table showing a room-only and a breakfast rate. After release, the first
  checks' traces are read back to confirm the recorded wording, as release 1 does for
  reservations.
- Staging: the release probe runs a recorded check through selection on a production copy with a
  breakfast reservation and both kinds of offer.

## Rollout

One release with the rule enforced from the start. An observe-only mode was considered and not
chosen: it would keep sending the alert this intent exists to stop, and an uncertain reading
already fails toward excluding the offer.

## Prior decisions considered

- ADR-057: the rule and the reading. This bolt implements points 1, 4 and 5 and amends
  `AGENTS.md`.
- ADR-056 and ADR-055: Jev as price method or comparison arm; both pass through the same
  selection.
- ADR-043 and ADR-045: adapters return untrusted evidence; no adapter chaining.
- Intent 018: conclusive observations and the opportunity lifecycle.
- ADR-001: additive migrations.

## Plan departures (recorded 2026-10-12T22:38:30Z, before Stage 4)

The design was confirmed against the code and reduced to what the requirements and acceptance
criteria need. The owner switched the session to a smallest-complete-change mode on 2026-10-12.

- **No schema v22.** The alert is rendered in the same pass that produces the check result, so
  the offer's meal plan travels on the in-memory result. It is not stored in `check_history` or
  `savings_opportunities`.
- **`/savings`, the `/checknow` success text and the paired report are unchanged.** None is a
  requirement. A check whose offers were all excluded on meals already reports the exclusion
  counts in its existing no-equivalent-offer detail.
- **Migration fix is local.** `_migrate_v21` tolerates a column another connection has just
  added. Schema application is not restructured, so no addendum to ADR-001 is written.
- **One mapper serves Browser Use, Stagehand and Jev**, so the wording field is added once.
  Stagehand's extraction schema is not extended: it is an unused rollback path and its offers
  read `unknown`, which fails closed.
- **Legacy DOM-only parser is unchanged.** Its shortcut is simply not taken when the reservation
  includes meals, so the model extraction supplies the wording.
- **Read-back evidence**: the price diagnostic records each candidate's classified meal plan
  (the value, not the wording).

## Open points for the owner

1. Accept model-copied meal wording on the LLM price paths at the same trust level as their
   cancellation wording (recommended), or require those paths to report `unknown` until Jev is the
   price method.
2. Enforce from the first release (recommended) or observe first.
3. Include the serialized-migration fix in this bolt (recommended) or ship it separately.
4. One real rate-table example from Booking.com for the tests.
