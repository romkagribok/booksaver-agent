---
stage: plan
bolt: 033-conclusive-opportunity-lifecycle
created: 2026-07-27T02:34:15Z
---

# Implementation Plan: Conclusive Opportunity Lifecycle

## Objective

Make the latest conclusive persisted check—not the latest attempt and not merely the latest
historical positive row—the source of truth for rebook actionability.

## Deliverables

- Update single-booking and user-scoped current-opportunity queries to join savings rows to their
  originating check.
- Define the conclusive predicate as successful results plus `NO_EQUIVALENT_OFFER`.
- Reuse the same predicate in the atomic rebook-session insert guard.
- Generalize stale-selection Telegram guidance for both replacement and invalidation.
- Add focused tests for technical-failure preservation, smaller-saving replacement, successful
  non-saving invalidation, no-equivalent invalidation, later restoration, ownership/history, and
  session races.

## Dependencies

- Bolt 032 current-per-booking selection and stale-ID validation.
- Existing `check_history.check_id` and `savings_opportunities.check_id` linkage.
- Existing SQLite `BEGIN IMMEDIATE` transaction used by guided rebook session creation.

## Technical Approach

Join each candidate opportunity to its source `check_history` row. It remains current only if no
later check-history row for the booking is conclusive. Compare `check_history.id` values so ordering
matches persistence order even when timestamps are equal. A successful newer check with a saving
will have its own opportunity and become current; a successful non-saving or
`NO_EQUIVALENT_OFFER` check will have no opportunity and therefore leave no current row. Ignore all
other failure codes for supersession.

The session repository will run the same source-check and later-conclusive `NOT EXISTS` predicate
inside its existing immediate transaction. No schema or domain-object change is required.

## Acceptance Criteria

- [ ] Technical failures preserve the prior positive opportunity.
- [ ] A newer successful lower-than-baseline price becomes current, including smaller savings.
- [ ] A newer successful equal/above-baseline price invalidates current actionability.
- [ ] A newer `NO_EQUIVALENT_OFFER` invalidates current actionability.
- [ ] A later successful saving restores actionability.
- [ ] Picker, service, and transaction guards agree.
- [ ] Historical rows and ownership boundaries remain intact.
- [ ] Focused and full quality gates pass.
