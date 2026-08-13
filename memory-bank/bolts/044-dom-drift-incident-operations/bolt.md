---
id: 044-dom-drift-incident-operations
unit: 003-dom-drift-incident-operations
intent: 022-adaptive-booking-browser-resilience
type: ddd-construction-bolt
status: complete
stories:
  - 001-correlate-dom-drift-incidents
  - 002-notify-owner-of-maintenance-required
  - 003-retain-encrypted-incident-diagnostics
created: 2026-08-13T01:59:59.000Z
started: 2026-08-13T03:12:00.000Z
completed: "2026-08-13T03:30:09Z"
current_stage: null
stages_completed:
  - domain-model
  - technical-design
  - adr-analysis
requires_bolts:
  - 043-dom-resilient-browser-workflows
enables_bolts: []
requires_units:
  - 002-dom-resilient-browser-workflows
blocks: true
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 044-dom-drift-incident-operations

## Overview

Persist and correlate content-free DOM-drift occurrences, deliver deduplicated owner Telegram
maintenance alerts, and retain one locally encrypted seven-day diagnostic bundle per incident.

## Objective

Give the operator timely, actionable evidence whenever adaptive assistance indicates deterministic
Booking.com code has drifted, while keeping all page/account data off Telegram and ordinary logs and
ensuring incident work never disrupts browser cleanup.

## Stories Included

- **US-137**: Correlate DOM-drift incidents (Must)
- **US-138**: Notify owner of maintenance required (Must)
- **US-139**: Retain encrypted incident diagnostics (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: Complete → `ddd-01-domain-model.md`
- [x] **2. Technical Design**: Complete → `ddd-02-technical-design.md`
- [x] **3. ADR Analysis**: Complete → ADR-034 accepted
- [ ] **4. Implement**: In progress → persistence, bundle store, Telegram/CLI/status, retry/purge wiring
- [ ] **5. Test**: Pending → `ddd-03-test-report.md`

## Dependencies

### Requires

- `043-dom-resilient-browser-workflows` terminal diagnosis and structural fingerprint input.
- Existing deployment secret, SQLite migrations, Telegram owner identity/sender, maintenance cycle,
  purge service, CLI, and `/status` interfaces.

### Enables

- Operations build/deploy/verification planning after all intent-022 construction bolts complete.

## Expected Outputs

- Restart-safe incident aggregate, occurrence fingerprinting, deduplication, and resolution.
- Owner-only content-free notification with bounded retry and delivery audit.
- Encrypted/sanitized diagnostic envelope, owner inspection command, and seven-day purge.
- Schema/config/status documentation plus privacy/adversarial tests.

## Success Criteria

- [ ] Maintenance diagnosis alerts immediately; repeated assisted drift alerts on occurrence two.
- [ ] Later deterministic success resolves the incident; assisted success alone does not.
- [ ] Telegram/logs contain no page, account, user, reservation, model-response, or secret content.
- [ ] Evidence is encrypted locally and unavailable after seven days or applicable purge.
- [ ] Evidence/encryption/Telegram failure remains explicit without suppressing the incident.
- [ ] Incident work never starts browser work or delays cleanup.
- [ ] Focused and full relevant quality gates pass.

## Notes

Construction, live model replay, commit, push, merge, and deployment remain separately gated.
