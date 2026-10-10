---
id: 003-state-meals-in-alerts
unit: 002-meal-aware-offers
intent: 027-meal-plan-equivalence
status: draft
priority: must
created: "2026-10-10T01:49:45Z"
assigned_bolt: 091-meal-aware-offers
implemented: false
---

# US-224: State meal plans in savings alerts

## User story

As a BookSaver user, I want every savings alert to state my reservation's and the offer's
meal plan, so that I can see the comparison for myself.

## Assigned requirement

FR-8, FR-9.

## Acceptance criteria

- [ ] Given a savings alert, when it is sent, then it states both meal plans in plain words.
- [ ] Given a reservation whose meal plan is `unknown`, when an alert is sent, then it says the
  reservation's meals could not be confirmed.
- [ ] Given a saved opportunity found before the reservation's meal plan was known, when the meal
  plan becomes known, then the opportunity is re-evaluated.

## Out of scope

Changing alert delivery channels.
