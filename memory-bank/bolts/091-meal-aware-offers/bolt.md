---
id: 091-meal-aware-offers
unit: 002-meal-aware-offers
intent: 027-meal-plan-equivalence
type: ddd-construction-bolt
status: complete
stories:
  - 001-read-offer-meal-plans
  - 002-exclude-worse-meal-offers
  - 003-state-meals-in-alerts
  - 004-apply-meal-rule-to-every-price-method
created: "2026-10-10T01:49:45Z"
started: "2026-10-10T08:20:49Z"
completed: "2026-10-13T13:51:59Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: "2026-10-10T08:21:20Z"
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: "2026-10-10T08:22:31Z"
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: "2026-10-12T22:38:30Z"
    artifact: ../090-reservation-meal-plan/adr-057-meal-plan-equivalence.md
  - name: implement
    completed: "2026-10-12T22:48:46Z"
    artifact: src/booksaver/domain/offer.py
requires_bolts:
  - 090-reservation-meal-plan
enables_bolts: []
requires_units: []
blocks: true
complexity:
  avg_complexity: 3
  avg_uncertainty: 3
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 091-meal-aware-offers

## Overview

Read each offer's meal plan, gate offer selection on it, and state both meal plans in alerts.

## Objective

Stop reporting a cheaper offer that includes fewer meals than the reservation.

## Stories Included

- [ ] US-222: Read each offer's meal plan (001-read-offer-meal-plans; Must)
- [ ] US-223: Exclude offers with a worse meal plan (002-exclude-worse-meal-offers; Must)
- [ ] US-224: State meal plans in savings alerts (003-state-meals-in-alerts; Must)
- [ ] US-225: Apply the meal rule to every price method (004-apply-meal-rule-to-every-price-method; Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: written → ddd-01-domain-model.md (owner review pending, combined)
- [x] **2. Technical Design**: written → ddd-02-technical-design.md (owner review pending, combined)
- [x] **3. ADR Analysis**: addendum to ADR-057; no new ADR (see below)
- [x] **4. Implement**: src and tests (owner approved with Stage 5)
- [x] **5. Test**: ddd-03-test-report.md (construction, release and production read-back)

No stage has started. Owner instruction of 2026-10-10T08:07:38Z: "proceed to realease 2 following specsmd until
writing any code so i can review and approve, then you will write code for it". Stages 1 to 3 are
therefore written without a stop between them and presented together for one review; Stage 4
starts only after that approval. The stops after Stage 4 and Stage 5 apply as the bolt type
defines them.

## ADR analysis (2026-10-10T08:22:31Z)

ADR-057 (accepted) already records the equivalence rule and the reading rule. Two further
decisions in this bolt's design may warrant a record; they are put to the owner and nothing is
written until the owner selects:

1. **Offer meal wording on the LLM price paths is model-copied.** It has the trust level of the
   cancellation wording those paths already copy; a fabricated inclusion could admit an offer.
   Recommended: record as an addendum to ADR-057 rather than a new ADR.
2. **Schema application is serialized.** Migrations run under one immediate transaction that
   re-reads the version, after release 1 showed concurrent migration at daemon start.
   Recommended: record as an addendum to ADR-001 (SQLite persistence) rather than a new ADR.

Mapping a meal-only exclusion to the existing no-equivalent-offer observation follows intent 018
and needs no decision record.

## Owner review of Stages 1 to 3 (2026-10-12T22:38:30Z)

The agent presented the stage summary and five open points on 2026-10-10. The owner replied on
2026-10-12: "pls continue". The agent takes that as approval of Stages 1 to 3 with the
recommended options: model-copied meal wording accepted on the LLM price paths, the rule
enforced from the first release, the migration fix included in this bolt, and the first decision
recorded as an addendum to ADR-057. The owner did not supply a real rate-table example. The
owner's exact words are recorded so this reading can be corrected.

Bolt 090's production readings were reviewed first, as this bolt requires: "Breakfast is included
in the final price" reads `breakfast`, "No meal is included in this room rate." and "There is no
meal included in the rate for this apartment." read `none`.

## Owner review of Stages 4 and 5 (2026-10-12T22:56:19Z)

The agent presented the implementation, the test results, the cuts against the design and what
is not verified. The owner replied: "sounds good, merge, redeploy and monitor dads booking for
the next 24 hours to make sure it runs as expoected". That approves Stage 4, the construction
evidence of Stage 5, and the merge and production deployment, and asks for 24 hours of
monitoring of the reservation that includes breakfast. The bolt completes after that evidence.

## Owner confirmation of completion (2026-10-13T13:51:32Z)

After the production read-back the owner wrote: "so i think this can be marked as success then
and we can close this thread you agree?". The agent agreed on the evidence and pointed out that
it covers two of three scheduled checks and about 15 of the 24 hours asked for. Descoped and
unproven items are listed in the requirements amendment of the same time.

## Dependencies

### Requires

090-reservation-meal-plan released, and its production readings reviewed.

Bolt 090 was released on 2026-10-10T08:15:02Z but is not complete: its production readings are
not in yet (first synchronization after the release is scheduled for 09:51Z). The owner asked on
2026-10-10T08:07:38Z to proceed with this bolt's stages up to, but not including, code. The
readings will be reviewed before Stage 4 starts.

### Enables

None.

## Success Criteria

- [ ] All stories implemented
- [ ] All acceptance criteria met
- [ ] Tests passing
- [ ] Code reviewed

## Notes

Offer-side wording is qualified against saved real property pages; nothing is assumed from
memory. ADR-056 has made Jev selectable as the authoritative price method, so the Jev rate reader
is in scope as a price method, not only as a comparison arm.
