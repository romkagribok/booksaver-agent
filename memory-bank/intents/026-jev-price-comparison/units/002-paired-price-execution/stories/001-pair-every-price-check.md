---
id: 001-pair-every-price-check
unit: 002-paired-price-execution
intent: 026-jev-price-comparison
status: draft
priority: must
created: "2026-09-26T16:33:08Z"
assigned_bolt: 086-paired-price-execution
implemented: false
---

# US-209: Pair every eligible price check

## User story

As a user, I want to see both independent methods for every admitted price check, so the price comparison is trustworthy and actionable.

## Assigned requirement

FR-6; shared NFRs in ../../../requirements.md. The complete pair contract is in
../../../experiment-design.md.

## Acceptance criteria

- [ ] Given paired mode and eligible manual or scheduled work, when a booking check is admitted, then create one comparison with two method IDs using the same frozen booking/session inputs.
- [ ] Given an existing inventory prerequisite, when the pair executes, then discovery runs once on its existing path and its costs are common, not candidate inference.
- [ ] Given persisted counterbalanced order, when each arm runs, then it gets a fresh context under the sole lease and records observation times/provenance/gap; neither reads sibling evidence.
- [ ] Given ordinary failure of the first arm, when the second remains authorized and budgeted, then run it; global stop/revocation/cleanup failure instead creates an explicit not-run result.
- [ ] Given repeated scheduling callbacks or manual retries for the same logical operation, when admission deduplicates, then there is no second pair for that operation.

## Technical notes

Do not split users 50/50 or sample only successful baselines; both arms are planned for all admitted checks.

## Dependencies

Requires: US-207, US-208.
Assigned bolt: 086-paired-price-execution. Downstream dependencies are recorded in units.md and bolt frontmatter.

## Edge cases

Missing/ambiguous evidence is an explicit terminal, never guessed success. Interrupted or denied work
retains cost and method attribution. Recheck user/session authority at execution and delivery.

## Out of scope

Inventory conversion, Stagehand removal, autonomous booking actions, provider/payer fallback and
claims of qualification without evidence.
