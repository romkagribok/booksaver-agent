---
intent: 022-adaptive-booking-browser-resilience
phase: inception
status: stories-defined
updated: 2026-08-15T22:33:19.000Z
---

# Adaptive Booking Browser Resilience - Unit Decomposition

## Requirement-to-Unit Mapping

- **FR-1**: Register every DOM-sensitive browser postcondition → `002-dom-resilient-browser-workflows`
- **FR-2**: Classify the current page safely despite DOM drift → `002-dom-resilient-browser-workflows`
- **FR-3**: Recover or interpret every safe DOM-dependent step → `002-dom-resilient-browser-workflows`
- **FR-4**: Explain every terminal browser outcome → `002-dom-resilient-browser-workflows`
- **FR-5**: Escalate Sonnet 5 to Opus 5 on measured quality failure → `001-adaptive-model-policy`
- **FR-6**: Enforce job and deployment dollar ceilings → `001-adaptive-model-policy`
- **FR-7**: Qualify and monitor model recovery quality → `001-adaptive-model-policy`
- **FR-8**: Detect and correlate likely DOM-drift incidents → `003-dom-drift-incident-operations`
- **FR-9**: Notify the owner with actionable, content-free evidence → `003-dom-drift-incident-operations`
- **FR-10**: Retain encrypted diagnostics for seven days → `003-dom-drift-incident-operations`
- **FR-11**: Finalize verified remote authentication atomically → `002-dom-resilient-browser-workflows`
- **FR-12**: Verify remote authentication from Booking.com server evidence → `002-dom-resilient-browser-workflows`

Every functional requirement is assigned exactly once.

## Units Overview

### Unit 1: `001-adaptive-model-policy`

**Description**: Own the approved Sonnet 5/Opus 5 profiles, objective escalation triggers,
caller-safe routing, conservative dollar admission, restart-safe deployment-day spend, usage audit,
and replay qualification gates.

**Stories**:

- `001-escalate-sonnet-to-opus-on-quality-failure`
- `002-enforce-browser-job-and-daily-dollar-ceilings`
- `003-qualify-adaptive-model-profiles`

**Dependencies**: Existing provider-neutral `AgentBrain`, Anthropic adapters, caller-scoped client
factory, usage accounting, replay fixtures, config, and persistence.

### Unit 2: `002-dom-resilient-browser-workflows`

**Description**: Register every DOM-sensitive browser postcondition and apply exact deterministic
terminal mapping first, then fresh page-state classification, guarded adaptive navigation, typed
semantic interpretation, code verification, and reason-preserving propagation only where ambiguity
remains across authentication capture, inventory synchronization, and customer-search price checks.

**Stories**:

- `001-register-every-dom-sensitive-browser-step`
- `002-classify-current-page-with-llm-fallback`
- `003-recover-and-interpret-safe-dom-drift`
- `004-explain-every-terminal-browser-outcome`
- `005-finalize-verified-remote-authentication-atomically`

**Dependencies**: Unit 1, completed intent 021 recovery controller, Playwright adapter, account
synchronization, remote authentication capture, customer-search journey, offer extraction,
coordinator, ActionGuard, and deterministic domain verifiers.

### Unit 3: `003-dom-drift-incident-operations`

**Description**: Correlate unrecovered DOM failure fingerprints, notify the owner without user/page
content, and retain one encrypted seven-day diagnostic bundle for local code maintenance.

**Stories**:

- `001-correlate-dom-drift-incidents`
- `002-notify-owner-of-maintenance-required`
- `003-retain-encrypted-incident-diagnostics`

**Dependencies**: Unit 2 terminal diagnoses plus existing Telegram owner identity, local encryption,
SQLite migrations, maintenance cadence, user purge, and CLI/status diagnostics.

## Unit Dependency Graph

```text
[Existing guarded recovery + caller-scoped LLM access]
                         |
                         v
            [001-adaptive-model-policy]
                         |
                         v
       [002-dom-resilient-browser-workflows]
                         |
                         v
       [003-dom-drift-incident-operations]
                         |
                         v
       [Owner Telegram alert + local evidence]
```

## Execution Order

1. Establish model profiles, quality escalation, usage attribution, and dollar admission.
2. Put every DOM-sensitive workflow behind the adaptive policy and prove exact failure reasons.
3. Persist/deduplicate maintenance incidents, deliver owner alerts, and enforce evidence retention.
4. Run cross-unit offline tests and opt-in sanitized Sonnet/Opus replay qualification.

## Decomposition Validation

- Each unit has one cohesive responsibility and a typed interface to the next unit.
- Every FR maps to exactly one unit; every unit produces independently testable behavior.
- Dependencies are one-way and contain no cycle.
- All units remain part of the existing single-process deployment; "unit" denotes a construction
  boundary, not a new service or browser process.
