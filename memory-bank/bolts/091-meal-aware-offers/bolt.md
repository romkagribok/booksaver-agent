---
id: 091-meal-aware-offers
unit: 002-meal-aware-offers
intent: 027-meal-plan-equivalence
type: ddd-construction-bolt
status: planned
stories:
  - 001-read-offer-meal-plans
  - 002-exclude-worse-meal-offers
  - 003-state-meals-in-alerts
  - 004-apply-meal-rule-to-every-price-method
created: "2026-10-10T01:49:45Z"
started: null
completed: null
current_stage: null
stages_completed: []
requires_bolts: ['090-reservation-meal-plan']
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

- [ ] **1. Domain Model**: Pending → ddd-01-domain-model.md
- [ ] **2. Technical Design**: Pending → ddd-02-technical-design.md
- [ ] **3. ADR Analysis**: Pending → the equivalence decision is drafted in bolt 090 as ADR-057
- [ ] **4. Implement**: Pending → src and tests
- [ ] **5. Test**: Pending → ddd-03-test-report.md

No stage has started. Each stage stops for the owner's confirmation unless the owner waives it
for this bolt before it starts.

## Dependencies

### Requires

090-reservation-meal-plan released, and its production readings reviewed.

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
