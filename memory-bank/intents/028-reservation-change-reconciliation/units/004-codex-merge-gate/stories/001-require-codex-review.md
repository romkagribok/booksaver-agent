---
id: 001-require-codex-review
unit: 004-codex-merge-gate
intent: 028-reservation-change-reconciliation
status: draft
priority: must
created: "2026-11-03T01:23:31Z"
assigned_bolt: 096-codex-merge-gate
implemented: false
---

# US-232: Require the Codex review before merge

## User story

As the owner, I want merges gated on the Codex review, so that the gate works with the review tool
this repository actually runs.

## Assigned requirement

FR-9.

## Acceptance criteria

- [ ] Given a clean completed Codex review of the current head with no unresolved Codex thread, when
  the gate runs, then it passes.
- [ ] Given a missing, stale, unfinished or unresolved review, when the gate runs, then it blocks.
- [ ] Given a current Codex usage-limit notice from Codex itself, when the gate runs, then it prints
  `waived`, unless a Codex thread is unresolved.
- [ ] Given the repository guidance and pull-request template, when read, then they name this gate
  and no Bugbot gate remains.

## Out of scope

Rewriting historical records that mention Bugbot.
