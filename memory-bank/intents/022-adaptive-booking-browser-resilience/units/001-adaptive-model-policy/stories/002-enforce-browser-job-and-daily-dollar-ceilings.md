---
id: 002-enforce-browser-job-and-daily-dollar-ceilings
unit: 001-adaptive-model-policy
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-13T01:59:59.000Z
assigned_bolt: 041-adaptive-model-policy
implemented: true
---

# Story: Enforce Browser-Job and Daily Dollar Ceilings

## User Story

**As a** self-hosted BookSaver owner
**I want** adaptive recovery to have generous but hard dollar ceilings
**So that** stronger-model resilience cannot create unbounded provider spend

## Acceptance Criteria

- [ ] **Given** a provider call is proposed, **When** its conservative input/output reservation would
  exceed the remaining USD 1 coordinator-job or USD 10 deployment UTC-day allowance, **Then** the
  call does not start and returns the exact applicable cost reason.
- [ ] **Given** Sonnet calls remain possible, **When** admitting them would consume the allowance
  reserved for one eligible Opus diagnostic, **Then** further Sonnet work stops and the policy
  proceeds to or preserves the Opus opportunity.
- [ ] **Given** a call completes, **When** usage is available, **Then** actual integer-microdollar or
  exact-decimal usage is reconciled once; missing/interrupted usage is charged conservatively once.
- [ ] **Given** the daemon restarts or UTC date rolls over, **When** admission resumes, **Then** the
  persisted deployment ledger preserves the current day or starts the new day atomically.
- [ ] **Given** `/bookings`, `/checknow`, or a scheduled slot starts, **When** calls are admitted,
  **Then** all synchronization and price-check calls within that single coordinator admission share
  one USD 1 job ledger.
- [ ] **Given** the selected model has no versioned pricing entry, **When** a call is requested,
  **Then** admission fails closed with `model_pricing_unavailable`.

## Technical Notes

- Add transactional reservation/reconciliation rather than relying on in-memory call counters.
- Preserve current per-user checks and LLM-call allowances as independent fairness controls.
- Expose price-table version and safe remaining allowance in owner diagnostics.

## Dependencies

### Requires

- US-130 model profiles and current SQLite migration/usage infrastructure.

### Enables

- All adaptive recovery and diagnostic stories can spend safely.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Two admissions race for final daily allowance | Exactly one transactional reservation succeeds |
| Provider reports more tokens than reserved | Record actual cost and block later calls; emit safe overrun audit |
| Clock moves backward | UTC ledger never reopens an already exhausted day |
| Personal and owner-funded keys coexist | Deployment cap is shared; usage attribution remains caller/key correct |

## Out of Scope

- Provider billing reconciliation beyond reported/estimated token usage.
- Changing existing per-user daily check/call limits.
