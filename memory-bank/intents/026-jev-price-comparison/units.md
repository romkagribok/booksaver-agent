---
intent: 026-jev-price-comparison
phase: inception
status: units-defined
updated: "2026-09-26T16:33:08Z"
---

# Units and requirement traceability

These three modules ship in one daemon. They have testable interfaces and dependency ordering;
independent service deployment is not a goal. DDD bolt types intentionally override the project's
simple CLI default because of evidence, money, lifecycle and isolation complexity.

| Unit | Responsibility | Stories | Bolts |
|---|---|---|---|
| [001-jev-price-executor](units/001-jev-price-executor/unit-brief.md) | Own the independent Jev-only price method, provider access, safe browser decisions, grounded extraction and metered model calls. | 5 | 084-jev-price-executor, 085-jev-price-executor |
| [002-paired-price-execution](units/002-paired-price-execution/unit-brief.md) | Own pair admission, durable independent method outcomes, single-authority effects and user-visible dual reports. | 4 | 086-paired-price-execution |
| [003-price-comparison-qualification](units/003-price-comparison-qualification/unit-brief.md) | Own cohort analysis, representative qualification, safe activation/rollback and the eventual owner decision handoff. | 3 | 087-price-comparison-qualification, 088-price-comparison-qualification |

## One owner for each functional requirement

| FR | Unit | Story | Bolt |
|---|---|---|---|
| FR-1 | 001-jev-price-executor | US-204 | 084-jev-price-executor |
| FR-2 | 001-jev-price-executor | US-207 | 085-jev-price-executor |
| FR-3 | 001-jev-price-executor | US-205 | 085-jev-price-executor |
| FR-4 | 001-jev-price-executor | US-206 | 085-jev-price-executor |
| FR-5 | 001-jev-price-executor | US-208 | 085-jev-price-executor |
| FR-6 | 002-paired-price-execution | US-209 | 086-paired-price-execution |
| FR-7 | 002-paired-price-execution | US-210 | 086-paired-price-execution |
| FR-8 | 002-paired-price-execution | US-211 | 086-paired-price-execution |
| FR-9 | 002-paired-price-execution | US-212 | 086-paired-price-execution |
| FR-10 | 003-price-comparison-qualification | US-213 | 087-price-comparison-qualification |
| FR-11 | 003-price-comparison-qualification | US-214 | 088-price-comparison-qualification |
| FR-12 | 003-price-comparison-qualification | US-215 | 088-price-comparison-qualification |

All NFRs apply across units; the final qualification bolt verifies the integrated contracts.
Every story appears in exactly one bolt and in memory-bank/story-index.md.

## Dependency graph

```mermaid
flowchart LR
  B84[084 Feasibility] --> B85[085 Jev executor]
  B85 --> B86[086 Pairs and Telegram]
  B86 --> B87[087 Evidence report]
  B87 --> B88[088 Qualification and release controls]
  B88 --> O[Operations and observation]
```

The feasibility blocker is external capability, not another existing unfinished price qualification
bolt. Existing intent 023 qualification statuses remain untouched and are not inherited.
Implementation tests/fixtures can be delegated once domain contracts are agreed; avoid concurrent
coordinator/schema edits. Main implementation agent owns integration and final validation.
