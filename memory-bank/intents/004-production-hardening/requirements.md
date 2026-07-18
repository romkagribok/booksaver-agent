---
intent: 004-production-hardening
phase: inception
status: complete
created: 2026-07-18T17:30:28Z
updated: 2026-07-18T18:12:29Z
---

# Requirements: Production Hardening

## Intent Overview

Harden the completed agentic-monitoring and Telegram/VPS capabilities using evidence from the first
real production check. The deployed agent successfully reached Booking.com, but a calendar-layout
variation caused the scripted `fill_search` step to fail and the screenshot-aware LLM agent to repeat
the same click until its loop guard stopped the run. The deployment also exposed a missing packaged
SQLite schema resource and Telegram discoverability/usability gaps.

This is a brown-field reliability enhancement and defect-fix intent. It preserves the existing
architecture and safety model: the LLM remains the adaptive recovery mechanism for layout drift,
browser actions remain guarded, exact booking data remains authoritative, and no cancellation or
purchase action becomes autonomous.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Complete checks despite ordinary Booking.com layout drift | A `fill_search` calendar-control failure receives screenshot-aware recovery and can safely continue from exact booking data instead of repeating one click until failure | Must |
| Keep agent recovery bounded and safe | Repeated identical actions are detected before five duplicate browser executions, while forbidden actions and hard budgets remain terminal | Must |
| Make the VPS artifact self-contained | A built wheel contains the SQLite schema required to initialize a fresh `/data` volume | Must |
| Make Telegram operations discoverable and usable | `/start` and `/help` expose all supported commands, and displayed short booking IDs work with `/checks` when uniquely resolvable for that user | Must |

---

## Functional Requirements

### FR-1: Screenshot-aware recovery must adapt instead of repeating actions

- **Description**: When a scripted journey step escalates, the browser agent must continue to use
  current text and screenshot observations while detecting successful-but-unverified identical
  action proposals. It must refuse further duplicate execution early, record the refusal in the
  check trace, request a materially different action from a fresh observation, and retain the
  existing hard upper bound that ends a non-progressing loop.
- **Acceptance Criteria**:
  - The agent receives a screenshot on visual-tier entry and after a duplicate action is refused.
  - No more than two identical successful-but-unverified action proposals are executed against the
    browser before the next duplicate is blocked.
  - A blocked duplicate is recorded as an agent trace event and does not call the browser adapter.
  - Five identical proposals without verified progress still produce `AGENT_GAVE_UP`.
  - Adapter-level forbidden actions and existing call/token/cost budgets remain unchanged and
    terminal.
- **Priority**: Must
- **Related Stories**: US-037

### FR-2: `fill_search` must have a safe exact-data continuation

- **Description**: The LLM remains the first recovery path for a failed `fill_search` step. If that
  bounded recovery ends only because the agent gave up or exhausted its budget, the journey may
  continue through the existing read-only Booking.com search URL generated from the registered
  booking's trusted property, dates, and occupancy. All downstream property/context verification
  and offer-equivalence rules must still run.
- **Acceptance Criteria**:
  - The safe continuation applies only to `fill_search` and only after screenshot-aware LLM recovery
    returns `AGENT_GAVE_UP` or `BUDGET_EXCEEDED`.
  - The generated URL uses the persisted check-in, check-out, adult, child, and room values; it does
    not accept agent-generated booking parameters.
  - A guard rejection, navigation failure, bot wall, or any failure in a later journey step remains a
    failed check and cannot be bypassed.
  - Property identity and requested search context are verified after navigation before an offer can
    enter the savings pipeline.
- **Priority**: Must
- **Related Stories**: US-038

### FR-3: Distribution artifacts must include persistence resources

- **Description**: Python distributions used by Docker/VPS deployments must include the SQLite
  `schema.sql` resource that the persistence adapter loads at runtime.
- **Acceptance Criteria**:
  - A wheel built from the repository contains
    `booksaver/infrastructure/persistence/schema.sql`.
  - Initializing BookSaver from an installed wheel on an empty data directory does not fail with a
    missing-schema `FileNotFoundError`.
  - No schema contents or migration behavior change as part of this packaging fix.
- **Priority**: Must
- **Related Stories**: US-039

### FR-4: Telegram command discovery and booking identifiers must be consistent

- **Description**: The Telegram welcome/help responses must list the commands available to an
  authorized user, including registration and key-management operations. Booking identifiers shown
  in chat must be accepted by `/checks` when the prefix uniquely identifies one of the caller's own
  bookings.
- **Acceptance Criteria**:
  - `/start` returns a welcome message followed by the full command reference.
  - `/help` lists `/register`, `/setkey`, `/deletekey`, and `/admin` in addition to the existing
    read-only and rebook commands.
  - `/checks` accepts an exact booking UUID or a unique prefix of at least eight characters scoped to
    the requesting user.
  - Short, ambiguous, nonexistent, or another user's prefixes return the same non-disclosing
    not-found response.
- **Priority**: Must
- **Related Stories**: US-040

---

## Non-Functional Requirements

### Reliability

| Requirement | Metric | Target |
|-------------|--------|--------|
| Duplicate-action containment | Identical browser executions before intervention | At most 2 per unverified action sequence |
| Safe degradation | Recovery paths that preserve downstream verification | 100%; no offer bypasses context/equivalence checks |
| Regression safety | Automated suite after implementation | 100% pass (645/645 at inception evidence point) |

### Safety and Security

| Requirement | Metric | Target |
|-------------|--------|--------|
| Destructive-action guard | Reserve, checkout, payment, and cancellation actions initiated by recovery | 0 |
| Cross-user information disclosure | Booking-prefix resolution outside caller scope | 0 |
| Agent authority | Agent-authored dates/occupancy used by safe continuation | 0; persisted booking data only |

### Deployability

| Requirement | Metric | Target |
|-------------|--------|--------|
| Wheel resource completeness | Required runtime schema present in wheel inspection | 100% |
| Static quality gates | Ruff and mypy results | Clean |

---

## Constraints

### Technical Constraints

- Preserve the single-process daemon, synchronous Playwright adapter, plain Anthropic tool-use loop,
  SQLite persistence, and existing module boundaries.
- Use the existing exact search-URL builder and verification pipeline; do not introduce a second
  independent scraping strategy.
- The LLM remains the primary adaptation mechanism after scripted failure. Deterministic logic may
  bound repeated actions and provide a safe continuation from trusted data, but must not interpret
  layout-specific controls as the sole recovery strategy.
- Add no runtime dependency and create no new architectural decision unless construction identifies
  a genuine deviation from ADR-013 through ADR-017.

### Business Constraints

- Booking.com hotels only, refundable offers only, and existing equivalence rules remain unchanged.
- No autonomous cancellation, reservation, checkout, payment, or purchase.
- Self-hosted deployment only; no BookSaver-hosted backend.

---

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| Booking.com's read-only search URL continues to accept property, date, and occupancy query parameters | Safe continuation could land on a generic or mismatched page | Existing property and search-context verification must fail the check before extraction |
| A fresh screenshot plus explicit duplicate refusal helps the LLM choose a different action | The model may still propose the same action | Keep the hard proposal limit and return `AGENT_GAVE_UP` without further browser execution |
| Eight UUID characters are normally unique within one user's small booking set | Two bookings may share a prefix | Resolve only unique prefixes; ambiguous prefixes fail closed |

---

## Open Questions

| Question | Owner | Resolution |
|----------|-------|------------|
| Should layout robustness be implemented as more calendar-specific selectors or through the screenshot-aware LLM? | Product owner | Resolved 2026-07-18: prioritize the screenshot-aware LLM so ordinary layout changes can adapt; deterministic code only bounds loops and preserves safe trusted-data continuation. |
| May a recovery bypass safety or downstream offer verification to complete more checks? | Product owner / architecture constraints | Resolved: no. Guard failures remain terminal and all normal property/context/equivalence checks remain mandatory. |
| Should this work alter completed intents 002 and 003 retrospectively? | AI-DLC process | Resolved: no. Record it as intent 004 with explicit dependencies on the completed capabilities. |

---

## Requirement Quality Checklist

- [x] All requirements are testable.
- [x] Acceptance criteria are binary.
- [x] Intent-specific NFRs have measurable targets.
- [x] Dependencies and constraints are identified.
- [x] Assumptions and mitigations are stated.
- [x] Requirements approved at AI-DLC Checkpoint 2 on 2026-07-18.
