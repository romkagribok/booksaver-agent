---
id: 085-jev-price-executor
unit: 001-jev-price-executor
intent: 026-jev-price-comparison
type: ddd-construction-bolt
status: in-progress
stories:
  - 002-access-typesafe-safely
  - 003-guard-jev-browser-decisions
  - 004-extract-complete-jev-price-evidence
  - 005-account-jev-provider-cost
created: "2026-09-26T16:33:08Z"
started: "2026-09-27T17:00:00Z"
completed: null
current_stage: live-acceptance
stages_completed:
  - name: domain-model
    completed: "2026-09-27T17:00:00Z"
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: "2026-09-27T17:00:00Z"
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: "2026-09-27T17:00:00Z"
    artifact: ddd-02-technical-design.md
  - name: implement
    completed: "2026-09-27T17:00:00Z"
    artifact: src/booksaver/infrastructure/browser/jev_price_executor.py
requires_bolts: ['084-jev-price-executor']
enables_bolts: ['086-paired-price-execution']
requires_units: []
blocks: true
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# 085-jev-price-executor

## Objective

Deliver the complete independent metered and guarded Jev price executor.

## Stories included

- [ ] US-205: Access TypeSafe safely (002-access-typesafe-safely; Must)
- [ ] US-206: Guard Jev browser decisions (003-guard-jev-browser-decisions; Must)
- [ ] US-207: Extract complete Jev price evidence (004-extract-complete-jev-price-evidence; Must)
- [ ] US-208: Account for Jev provider cost (005-account-jev-provider-cost; Must)

## Stages and expected outputs

- [ ] Domain model: ddd-01-domain-model.md with trust, ownership, failure and state contracts.
- [ ] Technical design: ddd-02-technical-design.md with source seams, interfaces and validation plan.
- [ ] ADR analysis: record actual new/amended decisions and update the decision index during construction.
- [ ] Implement: scoped source/tests, config/docs and migrations where required.
- [ ] Test: ddd-03-test-report.md with actual commands/results and each story criterion disposition.

Offline stages are complete; the test stage stays open until live acceptance evidence exists. Definition: .specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md.

## Dependencies and handoff

Required bolts: 084-jev-price-executor.
Enables: 086-paired-price-execution.
Cross-unit dependencies are expressed by these bolt references, not a whole-unit completion cycle.
Read memory-bank/intents/026-jev-price-comparison/implementation-handoff.md and this unit's brief first.

## Success criteria

- [ ] All included acceptance criteria verified; no fabricated runtime evidence.
- [ ] Paired experiment scope and independence preserved.
- [ ] Safe failure, bounded resource and user-isolation cases tested.
- [ ] Documentation and canonical indexes reflect the actual status.

## Scope and qualification notes

Do not change inventory implementation or retire Stagehand. Follow requirements and experiment-design.md; no implicit provider fallback.
