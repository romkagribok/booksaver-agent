---
id: 002-qualify-paired-price-release
unit: 003-price-comparison-qualification
intent: 026-jev-price-comparison
status: draft
priority: must
created: "2026-09-26T16:33:08Z"
assigned_bolt: 088-price-comparison-qualification
implemented: false
---

# US-214: Qualify paired price release

## User story

As a owner, I want to know the experiment is safe and representative before activating it, so the price comparison is trustworthy and actionable.

## Assigned requirement

FR-11; shared NFRs in ../../../requirements.md. The complete pair contract is in
../../../experiment-design.md.

## Acceptance criteria

- [ ] Given adversarial browser and ambiguous offer fixtures, when qualification runs, then all guard, independence and unchanged-validation contracts pass with per-criterion evidence.
- [ ] Given baseline-only mode, when regression tests run, then inventory, existing price behavior, session handling and notifications remain correct.
- [ ] Given cloned state and exact Linux image, when testing migration/restart/resource/cleanup paths, then SQLite/FKs, costs, side-effect isolation and process/browser ownership pass.
- [ ] Given release checks, when a PR is prepared, then targeted tests and final relevant full gates pass and the current-head Bugbot requirement is met before merge.
- [ ] Given actual owner/invitee manual and scheduled checks after gated activation, when native Telegram is observed, then both rows arrive and costs/results match persisted records; simulations are labelled separately.

## Technical notes

Pre-release tests gate deployment; post-deploy native acceptance is a separate operational evidence gate. No live probe alongside production.

## Dependencies

Requires: US-213.
Assigned bolt: 088-price-comparison-qualification. Downstream dependencies are recorded in units.md and bolt frontmatter.

## Edge cases

Missing/ambiguous evidence is an explicit terminal, never guessed success. Interrupted or denied work
retains cost and method attribution. Recheck user/session authority at execution and delivery.

## Out of scope

Inventory conversion, Stagehand removal, autonomous booking actions, provider/payer fallback and
claims of qualification without evidence.
