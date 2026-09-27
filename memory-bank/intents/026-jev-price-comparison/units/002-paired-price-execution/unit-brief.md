---
unit: 002-paired-price-execution
intent: 026-jev-price-comparison
phase: inception
status: in-progress
unit_type: backend
default_bolt_type: ddd-construction-bolt
created: "2026-09-26T16:33:08Z"
updated: "2026-09-26T16:33:08Z"
---

# Paired price execution and Telegram

## Purpose and scope

Own pair admission, durable independent method outcomes, single-authority effects and user-visible dual reports.

This is a bounded module inside the existing daemon, not a new deployable service. The cli-tool
catalog normally suggests simple command bolts; DDD is selected explicitly because this unit changes
state, evidence, money or cross-user side-effect contracts rather than just command presentation.

## Assigned requirements

FR-6, FR-7, FR-8, FR-9. See ../../requirements.md for acceptance and all NFRs.

## Domain concepts and operations

PriceComparison, MethodRun, MethodBudget, ComparisonDelivery and baseline application receipt.

Implement only operations described by the stories below. Use explicit typed input/output contracts,
existing repository/transport ports and unchanged domain validation. Refer to ../../system-context.md
for current source seams and ../../experiment-design.md for the pair contract.

## Dependencies

Unit 001 for a qualified candidate executor; existing coordinator, inventory, user/session guards, savings and Telegram adapters.

## Story summary

Total: 4; Must: 4; Should: 0; Could: 0. All generated, unimplemented.

| Story | Title | Requirement | Status |
|---|---|---|---|
| US-209 | [Pair every eligible price check](stories/001-pair-every-price-check.md) | FR-6 | Planned |
| US-210 | [Isolate pair state and recovery](stories/002-isolate-pair-state-and-recovery.md) | FR-7 | Planned |
| US-211 | [Bound pair resources](stories/003-bound-pair-resources.md) | FR-8 | Planned |
| US-212 | [Report two Telegram results](stories/004-report-two-telegram-results.md) | FR-9 | Planned |

## Planned bolts

086-paired-price-execution. Individual metadata lives under memory-bank/bolts/.

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
