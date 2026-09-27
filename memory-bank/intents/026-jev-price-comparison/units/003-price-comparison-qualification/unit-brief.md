---
unit: 003-price-comparison-qualification
intent: 026-jev-price-comparison
phase: inception
status: stories-defined
unit_type: backend
default_bolt_type: ddd-construction-bolt
created: "2026-09-26T16:33:08Z"
updated: "2026-09-26T16:33:08Z"
---

# Comparison evidence and delivery

## Purpose and scope

Own cohort analysis, representative qualification, safe activation/rollback and the eventual owner decision handoff.

This is a bounded module inside the existing daemon, not a new deployable service. The cli-tool
catalog normally suggests simple command bolts; DDD is selected explicitly because this unit changes
state, evidence, money or cross-user side-effect contracts rather than just command presentation.

## Assigned requirements

FR-10, FR-11, FR-12. See ../../requirements.md for acceptance and all NFRs.

## Domain concepts and operations

ExperimentCohort, ComparisonSummary, QualificationEvidence, ActivationProfile and RollbackVerification.

Implement only operations described by the stories below. Use explicit typed input/output contracts,
existing repository/transport ports and unchanged domain validation. Refer to ../../system-context.md
for current source seams and ../../experiment-design.md for the pair contract.

## Dependencies

Units 001 and 002 for metered paired outcomes; existing operations release workflow and final-head review gates.

## Story summary

Total: 3; Must: 3; Should: 0; Could: 0. All generated, unimplemented.

| Story | Title | Requirement | Status |
|---|---|---|---|
| US-213 | [Analyze paired results](stories/001-analyze-paired-results.md) | FR-10 | Planned |
| US-214 | [Qualify paired price release](stories/002-qualify-paired-price-release.md) | FR-11 | Planned |
| US-215 | [Activate and roll back comparison](stories/003-activate-and-rollback-comparison.md) | FR-12 | Planned |

## Planned bolts

087-price-comparison-qualification, 088-price-comparison-qualification. Individual metadata lives under memory-bank/bolts/.

## Constraints and success criteria

- [ ] Every assigned story criterion has test/evidence coverage and a reviewed outcome.
- [ ] No unrelated inventory/Stagehand/provider-framework expansion.
- [ ] Caller, cost, deadline, evidence and browser authority remain inspectable.
- [ ] Construction records design/ADR decisions and actual test evidence; no stage is pre-completed.

## External dependencies and data

TypeSafe availability and Booking.com DOM are external uncertainties; synthetic fixtures do not prove
live provider quality. Telegram delivery is not transactionally atomic with SQLite. Keep state local
and purgable by user; raw model/page text is excluded from normal persisted diagnostics. Dependency
selection and retained diagnostic lifetime must be settled explicitly in construction design.
