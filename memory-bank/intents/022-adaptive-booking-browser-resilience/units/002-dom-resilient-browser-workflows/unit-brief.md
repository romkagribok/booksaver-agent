---
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
phase: construction
status: complete
created: 2026-08-13T01:59:59.000Z
updated: 2026-08-16T16:35:00.000Z
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: DOM-Resilient Browser Workflows

## Purpose

Ensure every automated DOM-sensitive Booking.com step either reaches a code-verified postcondition,
ends immediately under an exact deterministic known reason, or uses guarded adaptive assistance to
resolve genuine ambiguity. The final actionable reason and provenance survive all mappings.

## Scope

### In Scope

- Exhaustive typed registry for account, authentication-capture, and customer-search DOM steps.
- Fresh tri-state/multi-state page classification with protected-state precedence.
- Zero-call termination for conclusive deterministic authentication, bot-wall, destination,
  observation, provider, budget, and other known outcomes.
- Sonnet/Opus recovery and typed interpretation for safe navigation and positive visible facts.
- Controlled adoption of one allowlisted read-only popup.
- DOM-independent semantic verifier evidence guarded by trusted domain comparison.
- DOM-independent `/connect` verification from a versioned read-only Booking server contract.
- Specific terminal taxonomy, reauth propagation, caller guidance, and redacted audit.

### Out of Scope

- Model selection and dollar accounting internals, owned by Unit 1.
- Incident correlation, owner alerts, and encrypted evidence retention, owned by Unit 3.
- Model interaction with credentials, MFA, captcha, account settings, or transactional controls.
- Model authority over identity, completeness, equivalence, refundability, currency, or mutation.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Register every DOM-sensitive browser postcondition | Must |
| FR-2 | Classify the current page safely despite DOM drift | Must |
| FR-3 | Recover or interpret every safe DOM-dependent step | Must |
| FR-4 | Explain every terminal browser outcome | Must |
| FR-11 | Finalize verified remote authentication atomically | Must |
| FR-12 | Verify remote authentication from Booking.com server evidence | Must |

## Domain Concepts

- **DomStepDefinition**: Named journey step, postcondition, safe capabilities, classifier and reason map.
- **PageStateClassification**: Validated current state, confidence, evidence categories, and action ban.
- **SemanticStepObservation**: Typed model-visible facts compared with trusted inputs by code.
- **ResilienceEpisode**: Deterministic failure, model attempts, guarded outcomes, verification, and stop.
- **TerminalBrowserDiagnosis**: Exact category, provenance, named step, safe action, and maintenance flag.
- **AdoptablePopup**: One allowlisted read-only child page validated before control transfer.
- **RemoteAuthFinalization**: Verified, non-viewer-cancellable session-capture phase whose success is
  committed only after encrypted persistence; administrative purge and shutdown remain authoritative.
- **RemoteAuthSessionContract**: Versioned signed-out/signed-in response distinction for one literal
  read-only Booking account endpoint, proven in fresh isolated contexts.
- **EdgePendingNegativeControl**: Exact cookie-free `202 text/html`, empty-body, no-redirect response
  admitted only as signed-out/pending evidence and never as authenticated evidence.
- **RemoteAuthServerReceipt**: Fresh, single-use code authority bound to caller, attempt, contract,
  expiry, and the exact verified cookie-snapshot digest.

## Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| Register step | Declare all recovery and terminal behavior | Journey/step/verifier/capabilities | Validated definition |
| Classify page | Determine protected or supported current state | Fresh bounded observation | Typed state or exact unavailable reason |
| Recover step | Propose guarded navigation from current evidence | Definition, policy, model router | Verified success or diagnosis |
| Interpret facts | Produce positive typed observations | Bounded current evidence, schema | Validated facts or exact rejection |
| Map outcome | Preserve diagnosis through workflow/coordinator | Resilience result | Domain failure/session/user guidance |
| Finalize authentication | Commit verified cookies and terminal state | Verification receipt, cookies, cancellation source | Persisted session or typed failure |
| Verify remote authentication | Establish negative baseline and verify immutable candidate twice | Fixed server contract, isolated contexts, candidate snapshot | Bound receipt or typed exact failure |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 7 |
| Must Have | 7 |
| Should Have | 0 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-133 | Register every DOM-sensitive browser step | Must | Complete |
| US-134 | Classify the current page with LLM fallback | Must | Complete |
| US-135 | Recover and interpret safe DOM drift | Must | Complete |
| US-136 | Explain every terminal browser outcome | Must | Complete |
| US-140 | Finalize verified remote authentication atomically | Must | Complete |
| US-141 | Verify remote authentication from server evidence | Must | Complete |
| US-142 | Admit the observed edge-pending negative control safely | Must | Complete |

## Dependencies

### Depends On

- `001-adaptive-model-policy`.
- Intent 021 shared `BrowserAgent` recovery and inventory interpreter.
- Current Playwright adapter, remote-auth runner, inventory source, search journey/check job,
  ActionGuard, domain verifiers, session manager, coordinator, Telegram formatting, and traces.

### Depended By

- `003-dom-drift-incident-operations` consumes terminal diagnoses and sanitized fingerprints.

### External Dependencies

- **Booking.com**: Unversioned dynamic DOM and page behavior - Risk: High.
- **Anthropic API**: Untrusted adaptive classification/navigation/interpretation - Risk: High.

## Technical Context

- Replace boolean authentication inference with protected-state-first typed classification.
- Make model interpretation an alternate evidence adapter, never a verifier replacement.
- Normalize stop reasons at the shared resilience boundary before inventory/search-specific mapping.
- Separate authentication proof from inventory discovery: `/connect` uses only a code-owned server
  contract; account inventory remains a later DOM-resilient workflow.
- Extend popup handling narrowly; never accept arbitrary or mutating destinations.
- Keep all live browser admission in `CheckCoordinator` and reuse the current context/page.

## Constraints

- Every model action passes existing ActionGuard and destination checks.
- Protected pages are classification-only and cannot enter the action loop.
- Fresh current evidence is mandatory; stale pre-navigation observations cannot classify destination.
- Incomplete evidence preserves prior reservations/opportunities and cannot prove absence.
- URL, cookie, DOM, and model evidence cannot issue a `/connect` server receipt; the exact verified
  cookie snapshot must be the snapshot handed to atomic finalization.

## Success Criteria

### Functional

- [x] A coverage test proves every current DOM-sensitive step has exact terminal mapping and, when
  ambiguity can remain, an LLM fallback.
- [x] Changed login DOM with weak signed-in markers becomes `auth_required`, marks reauth, and guides
  `/connect` without a model action.
- [x] Changed account/search controls and one safe popup can recover without adding a selector.
- [x] Typed model facts can support semantic progress only after deterministic comparison.
- [x] Every terminal registered step preserves an exact reason and provenance to Telegram/audit.
- [x] A verified remote-auth result survives ordinary viewer closure, persists before success and
  recovered-incident publication, and closes the Mini App only after commit.
- [x] `/connect` verifies authentication from an isolated Booking server contract with zero DOM or
  model authority, while inventory discovery begins only after the session is committed.

### Non-Functional

- [x] Zero prohibited actions and zero false authenticated/complete/equivalent states.
- [x] Healthy deterministic workflows add zero LLM calls.
- [x] All failure, cleanup, and trigger paths are deterministic under fake browser/model tests.

## Bolt Suggestions

- `042-dom-resilient-browser-workflows`: registry and protected-state classification (US-133–134)
  after bolt 041.
- `043-dom-resilient-browser-workflows`: cross-journey recovery, semantic verification, popup policy,
  and terminal reason propagation (US-135–136) after bolt 042.
- `045-dom-resilient-browser-workflows`: production correction for changed mobile inventory DOM.
- `046-dom-resilient-browser-workflows`: atomic verified-session finalization and viewer lifecycle
  correction (US-140) after bolt 045.
- `047-dom-resilient-browser-workflows`: finalizing-expiry, failure-incident race, and delayed
  Bugbot merge-gate correction (US-140) after bolt 046.
- `048-dom-resilient-browser-workflows`: server-backed, DOM-independent remote-auth verification
  (US-141) after bolt 047.
- `049-dom-resilient-browser-workflows`: exact `202` edge-pending negative-control correction
  (US-142) after bolt 048.
