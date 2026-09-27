---
unit: 001-jev-price-executor
intent: 026-jev-price-comparison
phase: inception
status: stories-defined
unit_type: backend
default_bolt_type: ddd-construction-bolt
created: "2026-09-26T16:33:08Z"
updated: "2026-09-26T16:33:08Z"
---

# Complete Jev price executor

## Purpose and scope

Own the independent Jev-only price method, provider access, safe browser decisions, grounded extraction and metered model calls.

This is a bounded module inside the existing daemon, not a new deployable service. The cli-tool
catalog normally suggests simple command bolts; DDD is selected explicitly because this unit changes
state, evidence, money or cross-user side-effect contracts rather than just command presentation.

## Assigned requirements

FR-1, FR-2, FR-3, FR-4, FR-5. See ../../requirements.md for acceptance and all NFRs.

## Domain concepts and operations

ProviderProfile, PriceExecutionRequest, ObservationSnapshot, ActionCandidate, EvidenceSpan, ModelAttempt and exact cost.

Implement only operations described by the stories below. Use explicit typed input/output contracts,
existing repository/transport ports and unchanged domain validation. Refer to ../../system-context.md
for current source seams and ../../experiment-design.md for the pair contract.

## Dependencies

Existing PriceBrowserExecutor contract, trusted query/session and deterministic price validators. No dependency on pair storage or Telegram.

## Story summary

Total: 5; Must: 5; Should: 0; Could: 0. All generated, unimplemented.

| Story | Title | Requirement | Status |
|---|---|---|---|
| US-204 | [Prove Jev price feasibility](stories/001-prove-jev-price-feasibility.md) | FR-1 | Planned |
| US-205 | [Access TypeSafe safely](stories/002-access-typesafe-safely.md) | FR-3 | Planned |
| US-206 | [Guard Jev browser decisions](stories/003-guard-jev-browser-decisions.md) | FR-4 | Planned |
| US-207 | [Extract complete Jev price evidence](stories/004-extract-complete-jev-price-evidence.md) | FR-2 | Planned |
| US-208 | [Account for Jev provider cost](stories/005-account-jev-provider-cost.md) | FR-5 | Planned |

## Planned bolts

084-jev-price-executor, 085-jev-price-executor. Individual metadata lives under memory-bank/bolts/.

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
