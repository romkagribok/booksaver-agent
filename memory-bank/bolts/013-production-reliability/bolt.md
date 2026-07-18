---
id: 013-production-reliability
unit: 001-production-reliability
intent: 004-production-hardening
type: simple-construction-bolt
status: complete
stories:
  - 001-adapt-after-repeated-browser-actions
  - 002-continue-fill-search-from-trusted-data
  - 003-package-persistence-schema
  - 004-discover-commands-and-use-booking-prefixes
created: 2026-07-18T17:48:48Z
started: 2026-07-18T17:59:20Z
completed: 2026-07-18T18:12:12Z
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-18T18:02:53Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-18T18:08:02Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-18T18:11:59Z
    artifact: test-walkthrough.md
requires_bolts:
  - 007-agentic-escalation
  - 012-vps-deployment
enables_bolts: []
requires_units:
  - 002-agentic-escalation
  - 005-vps-deployment
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: 013-production-reliability

## Overview

A single cohesive production-hardening bolt based on evidence from the first real VPS check. It
contains repeated LLM browser actions before they reach Playwright, safely continues an exhausted
`fill_search` step from trusted persisted data, makes the installed wheel self-contained, and aligns
Telegram command discovery with the booking identifiers users are shown.

## Objective

Deliver a deployable BookSaver build that can adapt more effectively to ordinary Booking.com layout
drift without weakening action safety, search-context verification, user isolation, or existing
product constraints.

## Stories Included

- [x] **001-adapt-after-repeated-browser-actions / US-037**: Detect duplicate proposals, refuse
  excess browser executions, trace the refusal, and provide a fresh screenshot (Must).
- [x] **002-continue-fill-search-from-trusted-data / US-038**: After bounded LLM exhaustion, continue
  only `fill_search` from persisted exact search context and retain all downstream checks (Must).
- [x] **003-package-persistence-schema / US-039**: Include the SQLite schema in built wheels and verify
  the distribution contents (Must).
- [x] **004-discover-commands-and-use-booking-prefixes / US-040**: Show the complete Telegram command
  surface and resolve exact or unique caller-owned booking prefixes (Must).

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

The CLI-tool project type defaults to a simple bolt. This work changes integration and utility seams
without adding a new bounded context, entity lifecycle, persistence model, or architectural pattern.

## Stages

- ✅ **1. Plan**: Complete → `implementation-plan.md`
- ✅ **2. Implement**: Complete → source/tests + `implementation-walkthrough.md`
- ✅ **3. Test**: Complete → tests/static/package verification + `test-walkthrough.md`

Each stage requires its mandatory human checkpoint. Construction artifacts must note that source and
test work existed before the missing AI-DLC documentation was identified.

## Expected Outputs

- Bounded duplicate-action handling in the existing browser agent.
- Approved safe continuation in the existing search journey.
- Setuptools package-data declaration and packaging regression test.
- Complete Telegram help/start text and user-scoped booking-prefix resolution.
- Targeted regression tests plus full pytest, Ruff, mypy, diff, and wheel-content evidence.
- Simple-bolt plan, implementation walkthrough, test walkthrough, and construction log.

## Dependency Analysis

### Requires

- **007-agentic-escalation** (complete): Browser agent, screenshot tier, guard, budgets, and traces.
- **012-vps-deployment** (complete): Installed-wheel container deployment where the schema omission
  was observed.
- **Unit `002-agentic-escalation`** (complete): LLM takeover contracts.
- **Unit `005-vps-deployment`** (complete): VPS runtime/distribution contracts.

### Enables

- Review, git delivery, VPS image rebuild, and a live Telegram-triggered smoke check.

### Dependency Warnings

- None. All required bolts and units are complete; no circular dependency exists.

## Complexity Assessment

- **Complexity 2/3**: Several existing seams change, but each change is small and bounded.
- **Uncertainty 1/3**: The production trace, failure detail, and desired behavior are known.
- **Dependencies 2/3**: Relies on completed journey, agent, Telegram scoping, and packaging behavior.
- **Testing 2/3**: Unit/journey tests, static gates, and distribution inspection; live VPS smoke test
  follows after reviewed git delivery.

## Success Criteria

- [x] All four stories are implemented and their acceptance criteria verified.
- [x] Existing forbidden-action and budget behavior remains safe and bounded.
- [x] Existing property/search-context/equivalence verification remains mandatory.
- [x] Full pytest suite, Ruff, mypy, and `git diff --check` pass.
- [x] A built wheel contains `booksaver/infrastructure/persistence/schema.sql`.
- [x] Code and AI-DLC artifacts received human review before commit and push.

## Notes

- The implementation-order deviation is deliberate historical evidence, not a waiver of remaining
  AI-DLC checkpoints. No construction stage will be marked complete without its required review.
- No ADR is anticipated: this bolt applies ADR-013 through ADR-017, ADR-018, and ADR-019 without a
  new architectural decision or technology.
