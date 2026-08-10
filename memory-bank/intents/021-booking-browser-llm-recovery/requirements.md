---
intent: 021-booking-browser-llm-recovery
phase: construction
status: complete
created: 2026-08-02T18:07:49.000Z
updated: 2026-08-10T16:36:20.000Z
---

# Requirements: Booking Browser LLM Recovery

## Intent Overview

Make guarded LLM recovery a shared capability for every automated, read-only Booking.com browser
journey. Price checks already escalate selected scripted failures, but the current loop cannot
distinguish action execution from verified progress and account inventory discovery has no LLM
fallback at all. The result is repeated ineffective actions, full-budget timeouts, and brittle
`/bookings` refreshes when Booking.com changes its page structure.

This intent makes progress observable, detects semantic no-progress across changing element refs,
forces evidence-rich reorientation, and terminates unreachable work quickly. It then applies the
same guarded recovery to authenticated reservation inventory used by `/bookings`, post-`/connect`
refresh, `/checknow`, and scheduled checks. Deterministic parsing and verification remain primary;
LLM output is untrusted fallback evidence and cannot weaken completeness, identity, eligibility,
privacy, or human-only action boundaries.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Recover safely from Booking.com layout drift | Every eligible automated browser step has a named, verified LLM fallback | Must |
| Stop ineffective agent loops | No semantic action executes more than twice without verified page progress | Must |
| Restore resilient booking discovery | Navigation/layout failures in account inventory invoke caller-scoped guarded recovery | Must |
| Preserve trustworthy synchronization | LLM evidence never independently proves complete inventory or absence | Must |
| Make model quality measurable | Sanitized replay fixtures report completion, safe give-up, latency, actions, and usage | Must |

## Approved Product Direction

- Back every automated, read-only Booking.com journey with the same provider-neutral recovery
  contract. This includes customer-search price checks and authenticated account inventory.
- Keep human-controlled authentication browsers (`/connect` viewer and local headed login) outside
  LLM control; only the subsequent automated inventory refresh uses LLM recovery.
- Keep deterministic browser scripts and parsers as the primary path. Invoke LLM work only after a
  named scripted step fails or deterministic interpretation is inconclusive.
- Treat a normal browser action as progress only when a verified state signal changes, not merely
  because Playwright returned without raising.
- After two consecutive no-progress actions, attach a fresh screenshot and explicit outcome
  feedback. One further no-progress attempt terminates with a reason-coded result.
- Bound one recovery episode to at most four LLM calls and 60 seconds, within the existing broader
  per-check and per-user daily limits.
- Preserve provider-independent action guards, allowlisted Booking.com navigation, caller-scoped
  sessions, and the prohibition on reserve, cancel, purchase, payment, modification, or checkout.
- Permit validated LLM interpretation to add positively observed reservation facts, but require
  independent deterministic evidence before a synchronization run is `complete` or an unseen
  reservation becomes absent.
- Harden the current Anthropic behavior first. The provider-neutral evaluation contract will be
  reused by the separate multi-provider capability without adding a provider in this intent.

## Scope

### In Scope

- Structured before/after action outcomes and progress fingerprints.
- Semantic duplicate/no-progress detection independent of volatile element refs.
- Screenshot escalation and bounded step-local termination.
- Step-specific recovery goals and non-recoverable failure classification.
- Shared LLM accounting, caller-scoped key resolution, traces, and redacted diagnostics.
- Guarded recovery for account inventory entry, readiness, scope traversal, pagination/detail
  navigation, and inconclusive deterministic interpretation.
- Strict typed validation and provenance for LLM-derived positive reservation observations.
- Sanitized offline fixtures plus opt-in live-model replay evaluation.
- Telegram `/bookings` error rendering when refresh fails unexpectedly.
- AI-DLC decisions, operator documentation, and regression tests.

### Out of Scope

- New Booking.com selectors or a one-off production selector hotfix as the primary solution.
- LLM control of authentication, credential entry, MFA, account settings, or the remote viewer.
- Autonomous booking, cancellation, modification, payment, purchase, or final submission.
- Arbitrary model-generated URLs, CSS selectors, JavaScript, coordinate clicks, or computer-use APIs.
- Adding OpenAI or another provider, silent provider switching, or unrestricted model strings.
- Allowing LLM output alone to establish inventory completeness, absence, cancellation, or identity.
- Changing the verified customer-search price source or offer-equivalence rules.

## Functional Requirements

### FR-1: Report verified browser-action outcomes

- **Description**: Every agent-directed browser action must return structured evidence describing
  execution and verified state change so the model and controller can distinguish progress from an
  unchanged page.
- **Acceptance Criteria**:
  - The outcome records whether the action executed, any redacted error category, URL/title change,
    visible-page fingerprint change, interactive-element fingerprint change, popup count/change,
    and named-step verification result.
  - Fingerprints are deterministic, bounded, and exclude cookies, credentials, API keys, raw HTML,
    and full sensitive account identifiers.
  - The next model turn receives concise structured outcome feedback plus the fresh observation.
  - A Playwright call returning normally with unchanged state and failed verification is recorded as
    `no_progress`, not success.
  - Existing post-action blocked-URL checks remain authoritative before any result is accepted.
- **Priority**: Must
- **Related Stories**: US-122, US-123

### FR-2: Detect semantic no-progress and terminate accurately

- **Description**: The recovery controller must recognize ineffective behavior across ref changes
  and alternating targets, reorient once with visual evidence, and stop before consuming the full
  check budget.
- **Acceptance Criteria**:
  - Semantic action identity uses action type, normalized target role/label/href, and normalized
    value rather than the transient element ref alone.
  - No semantic action executes more than twice against an unchanged verified page state.
  - Two consecutive no-progress outcomes force a fresh screenshot on the next model decision,
    regardless of whether the actions raised exceptions.
  - One additional no-progress action after evidence-rich reorientation terminates the episode with
    `agent_no_progress` and a redacted step-specific explanation.
  - Each recovery episode is limited to four actual LLM calls and 60 wall-clock seconds, while the
    existing total step, LLM-call, and check-time budgets remain outer caps.
  - Captcha, authentication, allowlist, identity-conflict, and prohibited-action outcomes terminate
    or fail closed under their existing specific codes rather than being retried as layout drift.
- **Priority**: Must
- **Related Stories**: US-122, US-123

### FR-3: Use step-specific, evidence-rich LLM recovery

- **Description**: Each recoverable browser step must supply a narrow goal, deterministic
  postcondition, safe actions, known failure evidence, and explicit stop conditions to the shared
  agent brain.
- **Acceptance Criteria**:
  - Recovery context identifies the journey, named step, goal, verification condition, previous
    outcomes, remaining step-local budget, and current tier-1/tier-2 observation.
  - Price-search and account-inventory steps use distinct instructions without duplicating the agent
    loop or provider adapter.
  - The model is explicitly told when an action opened an unadopted popup, left the page unchanged,
    was refused by a guard, or failed verification.
  - `give_up` reasons are normalized into categories such as unreachable control, unsupported
    layout, authentication required, captcha, no progress, and unsafe action.
  - Provider responses remain untrusted and map only to the existing bounded action vocabulary.
- **Priority**: Must
- **Related Stories**: US-123, US-124

### FR-4: Back every automated Booking.com browser journey with guarded recovery

- **Description**: Scripted failures in automated read-only Booking.com journeys must enter the
  shared agent recovery boundary when the failure is safely recoverable.
- **Acceptance Criteria**:
  - Existing customer-search steps retain their current deterministic-first escalation behavior and
    gain the new progress-aware controller.
  - Account inventory defines named steps for entry/readiness, scope traversal, pagination/detail
    navigation, and deterministic interpretation.
  - `/bookings`, post-`/connect` synchronization, `/checknow` prerequisite synchronization, and
    scheduled synchronization all use the same inventory recovery path.
  - Human-driven login/viewer operations never invoke the LLM or expose credential controls to it.
  - All automated work remains serialized by the existing `CheckCoordinator` browser gate; no
    second browser, queue, scheduler, or background coordinator is introduced.
- **Priority**: Must
- **Related Stories**: US-124, US-126

### FR-5: Resolve LLM capability and usage by caller and operation

- **Description**: Inventory recovery must use the correct active user's permitted LLM capability
  and the same daily accounting rules as price-check recovery.
- **Acceptance Criteria**:
  - The client factory resolves an agent brain and optional inventory interpreter for an explicit
    local user and operation role; it never falls back to a different user's personal key.
  - Owner-funded and personal-key behavior retains current caller isolation and policy.
  - Every actual inventory-recovery LLM call consumes the caller's existing daily LLM allowance.
  - No remaining daily allowance degrades to deterministic-only synchronization and records that
    fallback was unavailable; it does not crash or borrow allowance.
  - Provider, model, role, prompt version, calls, and bounded usage metadata are recorded without
    secrets or cross-user detail.
- **Priority**: Must
- **Related Stories**: US-124, US-128

### FR-6: Recover account inventory navigation and interpretation

- **Description**: When deterministic account inventory navigation, readiness, or interpretation
  fails because Booking.com changed its supported web layout, BookSaver must attempt guarded LLM
  recovery and retain all conclusive positive evidence.
- **Acceptance Criteria**:
  - Navigation/readiness exceptions and unsupported-layout/extraction-ambiguous results invoke the
    appropriate named recovery step when authentication, allowlists, and budgets permit.
  - The agent may interact only with visible read-only account inventory controls and allowlisted
    Booking.com reservation/detail destinations.
  - A bounded interpreter may return typed candidate observations only from the current caller's
    bounded page text/screenshot; candidates pass strict domain parsing and identity checks before
    reconciliation.
  - Invalid, incomplete, conflicting, unsupported, or low-confidence candidates are rejected without
    inventing facts needed for eligibility.
  - Positive validated observations from an incomplete assisted run may be upserted under existing
    partial-run semantics.
  - Failure preserves the last conclusive synchronized inventory and returns a specific redacted
    recovery outcome instead of the generic `navigation_failed` result where evidence permits.
- **Priority**: Must
- **Related Stories**: US-126, US-127

### FR-7: Preserve authoritative completeness and safety boundaries

- **Description**: LLM assistance must never weaken the rules that make Booking.com inventory and
  monitoring trustworthy.
- **Acceptance Criteria**:
  - Only independently verified traversal of all required scopes and terminal pagination/detail
    work can mark inventory `complete`.
  - LLM output alone cannot mark unseen reservations absent, cancelled, completed, replaced, or
    ineligible.
  - Remote reservation identity remains required and caller-scoped; identity ambiguity fails closed.
  - Account pages remain booked-fact sources only and never become replacement-price sources.
  - ActionGuard blocks reserve, book, cancel, modify, checkout, payment, purchase, and account-setting
    targets regardless of prompt or provider output.
  - Prompt-injected page text cannot expand tools, select arbitrary URLs, or override domain checks.
- **Priority**: Must
- **Related Stories**: US-127

### FR-8: Evaluate and audit recovery behavior reproducibly

- **Description**: BookSaver must provide a privacy-safe evaluation surface for measuring current
  and future navigation-agent profiles against real failure shapes.
- **Acceptance Criteria**:
  - Sanitized fixtures cover the production no-href/new-window property failure, unchanged-page
    alternating clicks, account inventory readiness drift, scope-control drift, unsupported layout,
    and adversarial prohibited controls.
  - Ordinary unit/integration tests remain offline and deterministic through fake brains and fake
    browsers.
  - An opt-in live-model replay command runs a curated profile multiple times without opening
    Booking.com, reports pass rate, action count, latency, LLM calls, usage, and outcome category,
    and never prints prompts containing reservation or session data.
  - Acceptance evaluation uses ten runs per solvable/unreachable fixture: at least nine must recover
    correctly or give up accurately; safety fixtures require zero prohibited action executions.
  - Recovery traces record structured outcomes and semantic loop decisions but never chain-of-thought.
- **Priority**: Must
- **Related Stories**: US-125, US-128

### FR-9: Present inventory recovery outcomes clearly

- **Description**: `/bookings` and operator diagnostics must distinguish authentication, guarded
  recovery, incomplete evidence, and unexpected worker failure without exposing another user's data.
- **Acceptance Criteria**:
  - `/bookings` continues to acknowledge promptly while browser work runs.
  - Assisted success identifies that recovery was used without exposing model internals.
  - Incomplete or failed refresh renders preserved stale reservations with a clear caller-scoped
    freshness warning and retry or `/connect` guidance.
  - An unexpected worker exception cannot be rendered as “No future reservations found.”
  - Logs and traces identify journey, step, result category, call/action counts, and timing using
    redacted local identifiers.
- **Priority**: Must
- **Related Stories**: US-128

### FR-10: Recover initial inventory navigation from current evidence

- **Description**: When the first authenticated inventory navigation raises after changing browser
  state, recovery must classify and operate from a fresh post-failure observation rather than the
  pre-navigation page.
- **Acceptance Criteria**:
  - Recovery obtains a new bounded observation after an entry/readiness exception and uses it for
    authentication, captcha, and reservation-page allowlist decisions.
  - A stale pre-navigation `about:blank` observation never overrides an available current
    Booking.com reservation-page observation.
  - The pre-navigation observation may remain the progress baseline for deterministic verification,
    but it is never treated as authoritative evidence of the current destination.
  - If the current page cannot be observed, recovery fails unavailable without invoking the LLM or
    acting from stale evidence.
  - A current authentication, captcha, external, or prohibited destination still fails closed before
    any LLM call or browser action.
  - Content-free diagnostics identify the named step, exception class, and approved/unapproved/
    unavailable destination category without logging URLs, queries, page text, reservation identity,
    cookies, or provider content.
  - Deterministic offline tests reproduce the production fresh-browser `about:blank` handoff and the
    unavailable/unapproved current-page boundaries.
- **Priority**: Must
- **Related Stories**: US-129

## Non-Functional Requirements

### Reliability

- **Step-local boundedness**: Every recovery episode completes within four LLM calls and 60 seconds;
  stricter outer limits may terminate it sooner.
- **No-progress control**: Zero third execution of the same semantic action against an unchanged
  state; one visual reorientation is attempted before `agent_no_progress`.
- **Fail-closed inventory**: 100% of incomplete/failed assisted runs preserve prior evidence and
  perform no absence-based lifecycle mutation.
- **Cleanup**: Browser pages, contexts, and the coordinator gate are released after success,
  give-up, provider error, budget breach, and unexpected exception.

### Security and Privacy

- **Action safety**: Zero prohibited browser actions across unit, integration, adversarial replay,
  and live smoke validation.
- **Caller isolation**: 100% of session, LLM-key, usage, trace, and synchronized-reservation access is
  resolved from the still-active caller; there is no owner/global/cross-user fallback.
- **Data minimization**: Prompts use bounded visible evidence and omit cookies, credentials, API
  keys, raw storage, and unnecessary full confirmation identifiers.
- **Human authentication**: Credential and MFA pages remain exclusively human-controlled.

### Performance and Cost

- **Happy path**: Deterministic successful journeys add zero LLM calls.
- **Recovery overhead**: Progress fingerprinting is local and bounded; it introduces no additional
  network request and no unbounded DOM scan.
- **Accounting**: Every actual provider call is counted once against existing per-user limits.
- **Evaluation**: Live-model replays are opt-in and never part of the default test suite.

### Observability and Testability

- **Trace coverage**: Every recovery records start, structured action outcomes, screenshot tier,
  termination reason, and final verification.
- **Determinism**: Offline tests inject clocks, brains, observations, and browser outcomes.
- **Compatibility**: Existing configs and Anthropic keys continue to work; new recovery-policy fields
  have validated defaults.
- **Navigation diagnostics**: Entry/readiness exceptions emit bounded machine-readable categories;
  raw destinations, exception messages, and account content remain excluded.

## Constraints

### Technical Constraints

- Preserve the single-process, synchronous Playwright, hexagonal, stdlib-first architecture.
- Reuse `AgentBrain`, `InteractiveBrowser`, `CheckCoordinator`, caller-scoped session vault, and
  current action guards rather than adding an agent framework.
- Keep LLM decisions provider-neutral at domain/application boundaries.
- Preserve ADR-015 tiered observations, ADR-016 bounded guarded actions, ADR-017 outer budgets,
  ADR-027 authoritative account inventory, and ADR-028 completeness-gated absence.

### Business Constraints

- BookSaver remains self-hosted and informational.
- Final reservation, cancellation, modification, payment, and purchase actions remain human-only in
  Booking.com.
- Commit, push, and pull-request preparation are authorized for this corrective bolt. Merge and
  deployment remain explicit review gates, and production live-model execution remains human-only.

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| The current browser adapter can expose bounded observations on inventory pages | Inventory recovery cannot reason about the changed page | Add only provider-independent observation fields, never raw handles or arbitrary selectors |
| Booking.com continues to expose a stable caller-scoped reservation identity somewhere in supported web evidence | Assisted observations cannot be safely reconciled | Persist partial failure and require reconnect/manual retry; never synthesize identity |
| Existing daily LLM counters can be shared with inventory recovery | Inventory calls could escape cost limits | Extend explicit user/role accounting before wiring recovery |
| The production incidents can be represented without private session data | Evaluation would risk privacy | Sanitize fixtures and keep raw failure snapshots owner-local and uncommitted |

## Open Questions

No blocking questions remain. The product owner approved autonomous progression through AI-DLC,
commit, push, and pull-request preparation, with review required immediately before merge.
