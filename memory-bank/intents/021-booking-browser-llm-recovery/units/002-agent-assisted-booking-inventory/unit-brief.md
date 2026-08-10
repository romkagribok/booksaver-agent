---
unit: 002-agent-assisted-booking-inventory
intent: 021-booking-browser-llm-recovery
phase: inception
status: complete
created: 2026-08-02T18:07:49.000Z
updated: 2026-08-10T16:36:20.000Z
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: Agent-Assisted Booking Inventory

## Purpose

Make authenticated Booking.com reservation discovery resilient to supported web-layout changes by
applying the shared guarded recovery controller and a strictly validated typed interpreter. Preserve
the account as authority, deterministic completeness proof, caller isolation, and read-only behavior.

## Scope

### In Scope

- Named inventory navigation/readiness/scope/detail/interpretation steps.
- Guarded agent recovery for recoverable navigation and layout failures.
- Typed LLM fallback for positive reservation observations.
- Deterministic validation, completeness gating, provenance, and partial-run reconciliation.
- Caller-scoped factory/usage integration and synchronization traces.
- `/bookings` assisted-success, incomplete, failure, busy, and unexpected-worker messaging.
- Shared use by `/bookings`, post-connect, `/checknow`, and scheduled synchronization.

### Out of Scope

- LLM selection of reservation identity when Booking.com exposes none or conflicting identities.
- Model assertion of inventory completeness, emptiness, cancellation, absence, or eligibility.
- Login, MFA, cancellation/modification controls, or live replacement-price extraction.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-6 | Recover account inventory navigation and interpretation | Must |
| FR-7 | Preserve authoritative completeness and safety boundaries | Must |
| FR-9 | Present inventory recovery outcomes clearly | Must |
| FR-10 | Recover initial inventory navigation from current evidence | Must |

## Domain Concepts

- **InventoryRecoveryStep**: Named read-only inventory goal with deterministic verifier.
- **InventoryInterpretation**: Untrusted typed candidates from bounded visible evidence.
- **ValidatedObservation**: Candidate that satisfies domain parsing and stable caller-owned identity.
- **TraversalEvidence**: Machine-observed scopes, terminal pagination, detail coverage, and emptiness.
- **AssistanceAudit**: Redacted per-run actions, calls, model role, timing, and outcome.

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 4 |
| Must Have | 4 |
| Should Have | 0 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-126 | Recover complete booking inventory discovery | Must | Ready |
| US-127 | Preserve completeness and safety under agent assistance | Must | Ready |
| US-128 | Explain and observe inventory recovery | Must | Ready |
| US-129 | Recover initial inventory navigation from current evidence | Must | Ready |

## Dependencies

- Unit `001-shared-booking-browser-recovery`.
- Existing synchronization domain/repository, encrypted sessions, inventory parser, coordinator,
  Telegram read-only commands, ADR-027, and ADR-028.

## Technical Context

- Refactor discovery into named steps without changing reconciliation authority.
- LLM interpretation is a separate typed port, not an `AgentAction` payload.
- Assisted positive observations retain explicit extraction provenance.
- Complete remains a deterministic traversal property; partial positives use current partial-run rules.

## Success Criteria

- [ ] Scripted success invokes zero LLM calls.
- [ ] Recoverable navigation/layout drift invokes caller-scoped guarded fallback.
- [ ] Positive assisted facts validate and reconcile without invented identity.
- [ ] LLM claims cannot archive unseen reservations or bypass eligibility rules.
- [ ] All four synchronization triggers use one fallback-capable path.
- [ ] `/bookings` never renders unexpected refresh failure as an empty account.
- [ ] Initial navigation exceptions re-observe the current page instead of classifying stale
  `about:blank` evidence.
- [ ] Current-page authentication, captcha, unapproved destination, and observation failure still
  stop before any LLM call or browser action.
- [ ] Navigation diagnostics expose only bounded exception and destination categories.
- [ ] Focused and full repository quality gates pass.

## Bolt Suggestion

- `039-agent-assisted-booking-inventory`: one DDD bolt after bolt 038.
- `040-agent-assisted-booking-inventory`: one corrective DDD bolt after production incident review.
