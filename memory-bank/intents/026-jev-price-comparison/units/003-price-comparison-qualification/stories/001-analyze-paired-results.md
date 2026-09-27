---
id: 001-analyze-paired-results
unit: 003-price-comparison-qualification
intent: 026-jev-price-comparison
status: draft
priority: must
created: "2026-09-26T16:33:08Z"
assigned_bolt: 087-price-comparison-qualification
implemented: false
---

# US-213: Analyze paired results

## User story

As a owner, I want to make an evidence-based adoption decision after repeated runs, so the price comparison is trustworthy and actionable.

## Assigned requirement

FR-10; shared NFRs in ../../../requirements.md. The complete pair contract is in
../../../experiment-design.md.

## Acceptance criteria

- [ ] Given a cohort, when generating its report, then include requested/preflight-excluded/admitted/completed/denied/failed counts and never filter failed arms out of success or spending denominators.
- [ ] Given shared inventory and uncertain charges, when reporting cost, then distinguish arm-only/common/all-in totals, cost per attempt/success and known versus conservative unresolved charges; count each inventory-run ID once in actual spend, allocate 1/N to its frozen admitted pairs, preserve zero-pair overhead, and distinguish hypothetical single-method totals from actual experiment spend.
- [ ] Given repeated runs, when comparing, then show paired differences, model/browser/end-to-end p50/p95, order/gap, provenance, failure classes, busy rejects and missed slots, stratified by booking/property/trigger.
- [ ] Given small correlated samples, when presenting success differences, then include suitable uncertainty and describe inconclusive results without treating 5–7 days as a qualification pass.
- [ ] Given changed model/prompt/adapter/settings, when storing/reporting, then start a new cohort; report generates no additional Booking.com/provider calls and never promotes or deletes code.

## Technical notes

Read-only owner CLI/local report; normal users see only their own pair. Suggested cost/success thresholds are decision aids, not auto-promotion.

## Dependencies

Requires: US-212.
Assigned bolt: 087-price-comparison-qualification. Downstream dependencies are recorded in units.md and bolt frontmatter.

## Edge cases

Missing/ambiguous evidence is an explicit terminal, never guessed success. Interrupted or denied work
retains cost and method attribution. Recheck user/session authority at execution and delivery.

## Out of scope

Inventory conversion, Stagehand removal, autonomous booking actions, provider/payer fallback and
claims of qualification without evidence.
