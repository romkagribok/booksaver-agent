---
stage: plan
bolt: 013-production-reliability
created: 2026-07-18T17:59:20Z
---

## Implementation Plan: production-reliability

### Objective

Harden the installed BookSaver daemon against the concrete production failures observed on the VPS:
contain non-progressing LLM browser actions, preserve screenshot-led adaptation with a safe
trusted-data continuation for only `fill_search`, ship the required SQLite schema in the wheel, and
make Telegram's documented command and booking-ID surfaces internally consistent.

### Stories Reviewed

- **US-037**: Adapt after repeated browser actions.
- **US-038**: Continue `fill_search` from trusted booking data.
- **US-039**: Package the persistence schema.
- **US-040**: Discover commands and use displayed booking identifiers.

### Deliverables

- Browser-agent duplicate proposal accounting that allows at most two identical
  successful-but-unverified executions, refuses later duplicates before Playwright, records the
  refusal, and supplies a fresh screenshot while retaining the five-proposal hard stop.
- Search-journey continuation that runs only after screenshot-aware `fill_search` recovery returns
  `AGENT_GAVE_UP` or `BUDGET_EXCEEDED`, then navigates using the existing trusted booking URL and
  passes through normal property/context/equivalence verification.
- Setuptools package-data configuration for the existing persistence `schema.sql` plus a regression
  test and built-wheel inspection.
- Telegram welcome/help text covering the complete supported command surface and `/checks`
  resolution for exact or unique caller-owned prefixes of at least eight characters.
- Targeted regression tests for duplicate execution containment, visual re-observation, safe fallback
  boundaries, user isolation/ambiguity, command discovery, and packaging metadata.
- An implementation walkthrough with no code excerpts and a test walkthrough with full verification
  evidence.

### Dependencies

- **Search journey (bolt 006)**: Existing exact URL builder and downstream property/search-context
  verification are reused; no parallel scraping path is introduced.
- **Agentic escalation (bolt 007)**: Existing screenshot tier, action signatures, adapter guard,
  budgets, trace recorder, and loop termination remain authoritative.
- **Telegram interface (bolts 008–010)**: Existing command router and caller-scoped repository port
  supply the operational surface and isolation boundary.
- **VPS deployment (bolt 012)**: Installed-wheel Docker build is the distribution path affected by
  the missing package resource.
- **Existing toolchain**: Python 3.11+, pytest, Ruff, mypy, setuptools wheel build, and archive
  inspection. No new runtime dependency.

### Technical Approach

1. Extend the browser-agent loop's existing action-signature history with an execution threshold
   distinct from the existing five-proposal give-up threshold. Refused duplicates become trace/tool
   feedback and force visual re-observation without reaching the guarded browser adapter.
2. Keep screenshot-aware LLM recovery first. At the journey orchestration seam, accept only the two
   bounded exhaustion outcomes for `FILL_SEARCH`; record the continuation and proceed to the existing
   exact search-results navigation. Do not catch guard rejection or any later-step failure.
3. Declare the SQL resource in setuptools package data. Verify both configuration and the archive
   produced by a real wheel build.
4. Centralize Telegram command discovery in the existing help text used by both `/help` and `/start`.
   Resolve booking references over `list_all_for_user` only; accept full IDs or unique prefixes of at
   least eight characters and fail closed for every other case.
5. Preserve module boundaries: browser adaptation remains in `monitor`, Telegram behavior remains in
   its infrastructure adapter, packaging remains in `pyproject.toml`, and tests mirror those seams.

### Safety and Failure Boundaries

- Reserve, checkout, payment, and cancellation actions remain blocked by the existing adapter guard.
- `BLOCKED_ACTION`, browser/navigation/bot-wall failures, and later journey-step failures remain
  terminal.
- Trusted URL parameters come only from the persisted booking; model output cannot change them.
- Property identity, date/occupancy context, room/refundability equivalence, and savings rules remain
  downstream gates.
- Booking-prefix resolution never queries outside the requesting user's scoped repository view and
  never distinguishes ambiguity from nonexistence in its response.

### Acceptance Criteria

- [ ] Visual-tier recovery includes the current screenshot on entry and after duplicate refusal.
- [ ] At most two identical successful-but-unverified actions execute before later duplicates are
  blocked and traced; five identical proposals still return `AGENT_GAVE_UP`.
- [ ] The exact-data continuation applies only to `FILL_SEARCH` plus `AGENT_GAVE_UP` or
  `BUDGET_EXCEEDED`, and all downstream verification remains active.
- [ ] Guard rejection and failures outside the approved continuation boundary remain failures.
- [ ] A built wheel contains `booksaver/infrastructure/persistence/schema.sql` and persistence
  behavior remains unchanged.
- [ ] `/start` and `/help` expose the complete command reference.
- [ ] `/checks` accepts full caller-owned IDs and unique caller-owned prefixes of at least eight
  characters; short, ambiguous, missing, and cross-user references fail identically.
- [ ] No runtime dependency, database schema version, or ADR is added.
- [ ] Full pytest suite, Ruff, mypy, `git diff --check`, and wheel inspection pass.

### Verification Plan

1. Run targeted browser-agent tests for duplicate proposals, adapter call count, trace output, hard
   loop termination, and screenshot refresh.
2. Run journey escalation/search-journey tests for successful LLM recovery, approved continuation
   codes, terminal guard behavior, and downstream verification.
3. Run Telegram command tests for help/start content, exact IDs, unique prefixes, ambiguity, short
   prefixes, and caller isolation.
4. Run packaging regression tests and build/inspect a wheel archive.
5. Run the entire pytest suite, Ruff, mypy, and whitespace validation.
6. Defer the live VPS image rebuild and Telegram-triggered Booking.com smoke check to Operations after
   reviewed implementation is committed and pushed.

### Chronology Deviation

The source and test changes were already present, uncommitted, when the missing AI-DLC documentation
was identified. This plan records the approved intended behavior at the first recoverable process
point. Stage 2 must compare the actual diff against this plan, correct any mismatch, and document the
result rather than claiming the plan preceded implementation.
