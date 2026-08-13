---
id: 041-adaptive-model-policy
unit: 001-adaptive-model-policy
intent: 022-adaptive-booking-browser-resilience
type: ddd-construction-bolt
status: complete
stories:
  - 001-escalate-sonnet-to-opus-on-quality-failure
  - 002-enforce-browser-job-and-daily-dollar-ceilings
  - 003-qualify-adaptive-model-profiles
created: 2026-08-13T01:59:59.000Z
started: 2026-08-13T02:25:43.000Z
completed: "2026-08-13T03:00:53Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-08-13T02:26:50.000Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-13T02:29:33.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-13T02:30:30.000Z
    artifact: adr-031-adaptive-sonnet-opus-routing-and-dollar-admission.md
  - name: implement
    completed: 2026-08-13T02:54:00.000Z
  - name: test
    completed: 2026-08-13T03:00:30.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 038-shared-booking-browser-recovery
  - 039-agent-assisted-booking-inventory
enables_bolts:
  - 042-dom-resilient-browser-workflows
requires_units:
  - 001-shared-booking-browser-recovery
  - 002-agent-assisted-booking-inventory
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 041-adaptive-model-policy

## Overview

Replace the single arbitrary browser-agent model with a fixed Sonnet 5 primary/Opus 5 escalation
portfolio, objective quality routing, restart-safe dollar admission, ordered usage audit, and
sanitized qualification gates.

## Objective

Deliver the reusable provider-neutral policy required by every adaptive browser workflow while
prohibiting Fable, preserving caller-key isolation, and enforcing USD 1 per coordinator job and
USD 10 per deployment UTC day before calls start.

## Stories Included

- **US-130**: Escalate Sonnet to Opus on quality failure (Must)
- **US-131**: Enforce browser-job and daily dollar ceilings (Must)
- **US-132**: Qualify adaptive model profiles (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. ADR Analysis**: Complete → ADR-031
- [x] **4. Implement**: Complete → model policy, config, persistence, adapters, replay reporting
- [x] **5. Test**: Complete → `ddd-03-test-report.md`

## Dependencies

### Requires

- `038-shared-booking-browser-recovery` for provider-neutral recovery/outcome contracts.
- `039-agent-assisted-booking-inventory` for caller-scoped interpreter/audit integration.
- Existing Anthropic client factory, configuration, SQLite migration, usage, and replay facilities.

### Enables

- `042-dom-resilient-browser-workflows`.

## Expected Outputs

- Typed Sonnet/Opus model profiles, escalation triggers, and ordered attempt audit.
- Transactional conservative call reservation and deployment UTC-day cost ledger.
- Config migration/defaults rejecting Fable/unpriced profiles.
- Expanded sanitized replay runner and release qualification report.

## Success Criteria

- [x] Only eligible measured quality failures escalate Sonnet work to Opus.
- [x] Safety/provider/budget terminals do not spend an ineffective escalation call.
- [x] No call starts beyond the USD 1/job or USD 10/deployment-day estimated ceiling.
- [x] Caller key isolation and existing per-user limits remain intact.
- [x] Replay qualification enforces accuracy and zero-prohibited-action gates.
- [x] Focused and full relevant quality gates pass.

## Notes

No provider call, production config change, commit, push, merge, or deployment is authorized by this
planned bolt. Construction begins only after inception Checkpoints 3 and 4.
