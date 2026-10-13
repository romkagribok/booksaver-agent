---
id: 089-jev-price-promotion
unit: 004-jev-price-promotion
intent: 026-jev-price-comparison
type: ddd-construction-bolt
status: complete
stories:
  - 001-price-discounted-rate-cards
  - 002-run-jev-as-the-price-method
  - 003-explain-unobserved-jev-runs
  - 004-recover-from-booking-error-page
created: "2026-10-10T01:45:00Z"
started: "2026-10-10T01:45:10Z"
completed: "2026-10-13T13:55:03Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: "2026-10-10T01:45:20Z"
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: "2026-10-10T01:45:40Z"
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: "2026-10-10T01:46:00Z"
    artifact: adr-056-jev-authoritative-price-method.md
  - name: implement
    completed: "2026-10-10T01:47:40Z"
    artifact: src/booksaver/infrastructure/browser/jev_primary_executor.py
requires_bolts:
  - 086-paired-price-execution
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 3
---

# 089-jev-price-promotion

## Objective

Make Jev selectable as the authoritative price method, fix discounted-rate pricing, and keep each
run explainable; leave the LLM price path in place as the rollback.

## Stories included

- [ ] US-216: Price member-discounted rate cards (001-price-discounted-rate-cards; Must)
- [ ] US-217: Run Jev as the price method with the LLM path as rollback (002-run-jev-as-the-price-method; Must)
- [ ] US-218: Explain Jev runs that produce no price (003-explain-unobserved-jev-runs; Must)
- [ ] US-219: Recover from Booking.com's transient error page (004-recover-from-booking-error-page; Must)

## Stage checkpoints

The owner pre-approved all five stages on 2026-10-07 ("Run through, review at end") and reviews
the artifacts in the pull request. The mandatory per-stage stops of the bolt type were therefore
waived for this bolt by explicit owner choice; this is recorded here and in the construction log.

## Delivery

Two phases, chosen by the owner on 2026-10-07 ("Fix, verify, then switch"):

1. Deploy with both methods still running; confirm the affected booking on a real scheduled check.
2. Switch production config to `price_executor = "jev"`, `jev_comparison.enabled = false`.

The bolt completes after phase 2 evidence, not before.

**Completion (2026-10-13T13:54:35Z).** Phase 2 evidence is recorded in the test report: six Jev-only checks,
all canonical successes, and the breakfast reservation selecting a breakfast rate. On
2026-10-13 the owner asked that finished work be closed in the AI-DLC records ("all interim work
should be finished until a new issue is picked so aidlc system should reflect that"). US-219's
production confirmation was never observed and is recorded as such.
