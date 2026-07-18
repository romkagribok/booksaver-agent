---
stage: implement
bolt: 013-production-reliability
created: 2026-07-18T18:05:35Z
---

## Implementation Walkthrough: production-reliability

### Summary

The implementation hardens four production seams without changing BookSaver's architecture or
adding a dependency. The browser agent now prevents repeated non-progressing execution while keeping
fresh screenshots available, the journey can continue only an exhausted `fill_search` step from
trusted booking data, installed wheels include the persistence schema, and Telegram's command/help
and booking-reference behavior are consistent.

During reconciliation, the action-guard path was tightened so a reservation-mutating proposal ends
the recovery with `BLOCKED_ACTION`; this prevents a later give-up code from qualifying for the safe
`fill_search` continuation.

### Structure Overview

The changes stay inside established seams. Agent-loop and search orchestration changes remain in the
monitor package, Telegram usability remains in the Telegram infrastructure adapter, distribution
metadata remains in the project configuration, and regression coverage remains in the corresponding
unit-test packages. Persistence schema contents, database migrations, domain equivalence rules,
rebook behavior, and deployment topology are untouched.

### Completed Work

- [x] `src/booksaver/monitor/browser_agent.py` - Contains repeated action proposals before excess
  browser execution, forces fresh visual feedback, retains bounded give-up, and makes destructive
  guard rejection terminal.
- [x] `src/booksaver/monitor/search_journey.py` - Allows only bounded `fill_search` exhaustion to
  continue through the existing trusted exact-results navigation while preserving later checks.
- [x] `src/booksaver/infrastructure/telegram/commands_readonly.py` - Provides complete command
  discovery and resolves full or unique caller-owned booking references without cross-user probing.
- [x] `pyproject.toml` - Declares the existing SQLite schema as persistence package data.
- [x] `tests/unit/monitor/test_browser_agent.py` - Covers bounded identical browser execution and
  screenshot-led loop recovery behavior.
- [x] `tests/unit/monitor/test_journey_escalation.py` - Covers safe `fill_search` continuation and
  terminal behavior for failures at other steps.
- [x] `tests/unit/monitor/test_search_journey.py` - Covers production-shaped calendar failure,
  screenshot-first escalation, trusted URL parameters, and journey continuation.
- [x] `tests/unit/telegram/test_commands_readonly.py` - Covers command discovery plus unique and
  ambiguous displayed booking prefixes.
- [x] `tests/unit/test_packaging.py` - Covers the setuptools persistence resource declaration.

### Key Decisions

- **Keep the LLM primary**: Scripted failure still escalates to the screenshot-aware agent first; the
  exact-data path is only a safe continuation after bounded exhaustion.
- **Separate adaptation from authority**: Screenshots help the model adapt, but the action guard,
  budgets, persisted booking values, and downstream verification define what it may accomplish.
- **Contain repeated execution early**: Two identical non-progressing browser executions are enough
  evidence to refuse later duplicates while still allowing the model more reasoning turns to choose
  a different action.
- **Treat destructive guard rejection as terminal**: Once the model proposes a known
  reservation-mutating target, the check stops with `BLOCKED_ACTION`; it cannot later be reclassified
  into a fallback-eligible give-up.
- **Reuse exact search navigation**: The implementation uses the existing Booking.com results URL
  builder and existing property/context verification instead of adding another scraping strategy.
- **Resolve identifiers within user scope**: Prefix uniqueness is computed only over bookings already
  filtered for the caller, preserving the non-disclosure boundary.
- **Package the resource explicitly**: The schema remains unchanged and is shipped through setuptools
  package data rather than copied by Docker-specific logic.

### Deviations from Plan

- **Chronology**: The initial source and test diff predated the recovered AI-DLC plan. Stage 2 compared
  that diff against the approved plan instead of representing the order differently.
- **Safety correction during reconciliation**: The preexisting implementation diff originally let
  the agent continue after a destructive guard rejection. Stage 2 changed this to terminal
  `BLOCKED_ACTION`, matching the approved failure boundary and preventing fallback misclassification.
- No scope, dependency, schema, architecture, or public-interface deviation was introduced.

### Dependencies Added

- [x] None - all changes use the existing Python runtime, Playwright/Anthropic integrations,
  setuptools configuration, and test toolchain.

### Implementation Validation

- [x] Ruff passed for `src/` and `tests/`.
- [x] `git diff --check` passed.
- [x] Source/test paths were matched to all four stories and plan deliverables.
- [ ] Behavioral tests, mypy, full suite, and wheel archive inspection are reserved for Stage 3.

### Developer Notes

The exact-results continuation is intentionally narrow: changing its accepted step or failure-code
set requires a new safety review. A live VPS image rebuild and Telegram-triggered Booking.com smoke
check cannot occur until this implementation is reviewed, committed, pushed, and deployed through
Operations.
