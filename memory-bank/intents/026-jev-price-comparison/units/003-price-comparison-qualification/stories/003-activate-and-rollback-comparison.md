---
id: 003-activate-and-rollback-comparison
unit: 003-price-comparison-qualification
intent: 026-jev-price-comparison
status: draft
priority: must
created: "2026-09-26T16:33:08Z"
assigned_bolt: 088-price-comparison-qualification
implemented: false
---

# US-215: Activate and roll back comparison

## User story

As a owner, I want to deploy a reversible multi-day experiment without premature cleanup, so the price comparison is trustworthy and actionable.

## Assigned requirement

FR-12; shared NFRs in ../../../requirements.md. The complete pair contract is in
../../../experiment-design.md.

## Acceptance criteria

- [ ] Given shipped code and paired mode disabled, when starting, then baseline behavior works without a TypeSafe key; paired activation requires model/key/disclosure and finite limits.
- [ ] Given qualified image/schema and final review, when deploying within authorized scope, then use restricted backups, preserve Caddy and verify process/logs/health/ports/dependencies/SQLite/browser cleanup.
- [ ] Given eligible users and a recorded cohort start, when paired mode activates, then every admitted manual/scheduled price check generates both method records and both Telegram results.
- [ ] Given a kill switch, restart or rollback, when stopping the experiment, then prevent new Jev arms, safely terminalize pending arms, retain history and resume baseline-only future checks with compatible schema.
- [ ] Given 5–7 days of observations, when producing the decision package, then owner chooses adoption/extension/rejection; Stagehand and inventory changes remain deferred until a separate decision.

## Technical notes

No automatic destructive cleanup, data-loss rollback, extra production polling or provider/payer fallback.

## Dependencies

Requires: US-214.
Assigned bolt: 088-price-comparison-qualification. Downstream dependencies are recorded in units.md and bolt frontmatter.

## Edge cases

Missing/ambiguous evidence is an explicit terminal, never guessed success. Interrupted or denied work
retains cost and method attribution. Recheck user/session authority at execution and delivery.

## Out of scope

Inventory conversion, Stagehand removal, autonomous booking actions, provider/payer fallback and
claims of qualification without evidence.
