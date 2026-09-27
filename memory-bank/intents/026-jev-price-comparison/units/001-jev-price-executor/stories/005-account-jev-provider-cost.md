---
id: 005-account-jev-provider-cost
unit: 001-jev-price-executor
intent: 026-jev-price-comparison
status: in-progress
priority: must
created: "2026-09-26T16:33:08Z"
assigned_bolt: 085-jev-price-executor
implemented: false
---

# US-208: Account for Jev provider cost

## User story

As a owner, I want to measure tiny Jev charges accurately alongside existing spending, so the price comparison is trustworthy and actionable.

## Assigned requirement

FR-5; shared NFRs in ../../../requirements.md. The complete pair contract is in
../../../experiment-design.md.

## Acceptance criteria

- [ ] Given a database containing historical Anthropic attempts, when migration runs, then all rows/FKs and existing pricing behavior are preserved while Jev identity is admitted explicitly.
- [ ] Given any dispatched attempt including retries, when completion/failure occurs, then its reservation reconciles exactly once to known usage or conservative unresolved charge.
- [ ] Given sub-microdollar costs, when accumulating/reporting, then no positive usage is silently treated as free and the rounding/precision policy is tested against provider-rate arithmetic.
- [ ] Given unknown model/pricing or a response-model mismatch, when accounting, then stop admission or conservatively reconcile without charging an unrelated model.
- [ ] Given a process crash after dispatch, when recovery runs, then uncertain reservations remain accounted for and no duplicate refund/charge is applied.

## Technical notes

Adapt the existing ledger rather than adding an ungoverned spend counter; retain actual tokens and price-table version.

## Dependencies

Requires: US-205.
Assigned bolt: 085-jev-price-executor. Downstream dependencies are recorded in units.md and bolt frontmatter.

## Edge cases

Missing/ambiguous evidence is an explicit terminal, never guessed success. Interrupted or denied work
retains cost and method attribution. Recheck user/session authority at execution and delivery.

## Out of scope

Inventory conversion, Stagehand removal, autonomous booking actions, provider/payer fallback and
claims of qualification without evidence.
