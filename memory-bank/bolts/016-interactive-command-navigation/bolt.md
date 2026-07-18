---
id: 016-interactive-command-navigation
unit: 001-interactive-command-navigation
intent: 005-telegram-command-navigation
type: simple-construction-bolt
status: complete
stories:
  - 001-discover-applicable-commands-natively
  - 002-route-and-authorize-interactive-callbacks
  - 003-select-bookings-and-savings-opportunities
  - 004-navigate-owner-administration-safely
created: 2026-07-18T22:14:33.000Z
started: 2026-07-18T22:14:33.000Z
completed: "2026-07-18T22:36:07Z"
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-18T22:14:33.000Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-18T22:28:16.000Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-18T22:30:55.000Z
    artifact: test-walkthrough.md
requires_bolts:
  - 012-vps-deployment
enables_bolts: []
requires_units:
  - 001-telegram-bot-gateway
  - 002-user-access-and-keys
  - 004-telegram-rebook-gate
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: 016-interactive-command-navigation

## Overview

Deliver native Telegram command discovery and inline selection for every enumerable input in the
current command surface.

## Objective

Let authorized users navigate `/checks`, `/rebook`, and `/admin` without remembering identifiers or
subcommand syntax while preserving typed paths, access scoping, and mutation confirmations.

## Stories Included

- [x] **001-discover-applicable-commands-natively / US-043**: Publish default and owner command menus (Must).
- [x] **002-route-and-authorize-interactive-callbacks / US-044**: Generalize guarded callback routing (Must).
- [x] **003-select-bookings-and-savings-opportunities / US-045**: Add user-scoped pickers (Must).
- [x] **004-navigate-owner-administration-safely / US-046**: Add confirmed owner menus (Must).

## Bolt Type

**Type**: Simple Construction Bolt.
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`.

## Stages

- ✅ **1. Plan**: Complete under continuous-flow authorization → `implementation-plan.md`.
- ✅ **2. Implement**: Complete under continuous-flow authorization → source/tests +
  `implementation-walkthrough.md`.
- ✅ **3. Test**: Complete under continuous-flow authorization → `test-walkthrough.md`.

Intermediate checkpoints were covered by the product owner's documented continuous-flow
authorization. The compressed validation was approved and the official completion script closed the
bolt on 2026-07-18T22:36:07Z.

## Dependencies

### Requires

- Completed Telegram gateway, user access, conversational operations, and rebook confirmation seams.

### Enables

- A command-menu and identifier-free Telegram smoke test on the VPS.

## Success Criteria

- [x] Applicable native command lists publish without making bot startup fragile.
- [x] Callback families route independently and are always authorized/acknowledged.
- [x] `/checks` and `/rebook` expose only caller-owned selectable entities.
- [x] `/admin` exposes actions and applies explicit confirmations to mutations.
- [x] Typed command behavior and rebook confirmation behavior remain compatible.
- [x] Focused/full pytest, Ruff, mypy, and new-artifact consistency checks pass.

## Notes

No new booking mutation command, dependency, schema, service, or process is included. The repository-
wide AI-DLC validators still report their pre-existing baseline: 34 legacy global-story-ID/filename
mismatches and four stale Bolt 009 story references. Intent 005 and Bolt 016 add no validator issue.
