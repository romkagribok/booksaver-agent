---
id: 004-extract-complete-jev-price-evidence
unit: 001-jev-price-executor
intent: 026-jev-price-comparison
status: draft
priority: must
created: "2026-09-26T16:33:08Z"
assigned_bolt: 085-jev-price-executor
implemented: false
---

# US-207: Extract complete Jev price evidence

## User story

As a user, I want to receive an independently validated complete Jev price result, so the price comparison is trustworthy and actionable.

## Assigned requirement

FR-2; shared NFRs in ../../../requirements.md. The complete pair contract is in
../../../experiment-design.md.

## Acceptance criteria

- [ ] Given frozen booking inputs and its own fresh context, when Jev runs, then independently reach the trusted query/property/rate evidence boundary and submit PriceExecutionResult without baseline observations.
- [ ] Given multiple rooms/rates/taxes/refund deadlines, when extracting, then select observed candidate spans linked to the correct room/rate and parse exact totals/dates/currency in code.
- [ ] Given wrong property/dates/occupancy, currency mismatch, ambiguous tax/refundability or missing evidence, when validating, then reject with the existing reason contract; never synthesize facts or conclusive no-offer.
- [ ] Given model DONE or a low headline price, when finalizing, then require independent completeness and the existing equivalence/refundability/all-in validators.
- [ ] Given a candidate end-to-end price run, when transport spies inspect inference, then zero Anthropic or other generative helper calls occur, including classification, extraction and diagnosis.

## Technical notes

Use structural candidate enumeration plus Jev span/record selection and deterministic assembly. Cross-record association is explicit; do not flatten away provenance.

## Dependencies

Requires: US-205, US-206.
Assigned bolt: 085-jev-price-executor. Downstream dependencies are recorded in units.md and bolt frontmatter.

## Edge cases

Missing/ambiguous evidence is an explicit terminal, never guessed success. Interrupted or denied work
retains cost and method attribution. Recheck user/session authority at execution and delivery.

## Out of scope

Inventory conversion, Stagehand removal, autonomous booking actions, provider/payer fallback and
claims of qualification without evidence.
