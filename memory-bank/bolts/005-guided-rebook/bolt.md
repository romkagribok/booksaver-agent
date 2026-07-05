---
id: 005-guided-rebook
unit: 004-guided-rebook
intent: 001-booksaver-agent-mvp
type: ddd-construction-bolt
status: complete
stories:
  - 001-start-guided-rebook-only-after-explicit-intent
  - 002-mandatory-confirmation-before-cancel-or-purchase
  - 003-log-rebook-outcomes-locally
created: 2026-07-05T00:00:00.000Z
started: 2026-07-05T00:00:00.000Z
completed: "2026-07-05T19:19:40Z"
current_stage: null
stages_completed:
  - name: model
    completed: 2026-07-05T00:00:00.000Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-05T00:00:00.000Z
    artifact: ddd-02-technical-design.md
  - name: adr
    completed: 2026-07-05T00:00:00.000Z
    artifact: adr-012-guided-final-click.md
  - name: implement
    completed: 2026-07-05T00:00:00.000Z
    artifact: src/booksaver/domain/rebook.py + application/rebook_service.py + cli_confirmation.py
  - name: test
    completed: 2026-07-05T00:00:00.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 001-core-local-data
  - 002-core-local-data
  - 003-booking-com-price-monitor
  - 004-savings-detection-notifications
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 2
---

# Bolt: 005-guided-rebook

## Overview

The safety-critical unit: an explicitly started, locally confirmed rebook flow. The
core deliverable is a **rebook session state machine** whose destructive transitions
(cancel existing / purchase new) are impossible without a fresh explicit confirmation,
plus a local append-only audit trail of every session event.

## Objective

`booksaver rebook <opportunity-id>` starts a session only on explicit intent (US-010);
every destructive step stops and requires an individual yes/no in the terminal (US-011);
every event is appended to local storage (US-012). The daemon on its own can never
cancel or purchase.

## Stories Included

- **US-010**: Start guided rebook only after explicit intent (Must)
- **US-011**: Mandatory confirmation before cancel or purchase (Must)
- **US-012**: Log rebook outcomes locally (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ✅ **1. Domain Model**: Complete → ddd-01-domain-model.md
- ✅ **2. Technical Design**: Complete → ddd-02-technical-design.md
- ✅ **3. ADR Analysis**: Complete → adr-012
- ✅ **4. Implement**: Complete → domain/rebook.py + rebook_service + gates
- ✅ **5. Test**: Complete → ddd-03-test-report.md (211/211)

## Dependencies

### Requires
- Bolt 004 (SavingsOpportunity records — the rebook entry point)
- Bolt 003 (BrowserSession port + Booking.com session reuse)
- Bolt 001 (Booking records, local store)

### Enables
- MVP completion (last MVP unit)

## Success Criteria

- [ ] No rebook automation runs without `booksaver rebook <id>` being invoked
- [ ] Cancel-existing and purchase-new each require a fresh explicit confirmation
- [ ] Declining any confirmation ends the session safely with no destructive action
- [ ] All session events appended to local storage (started, confirmation_requested,
      confirmed, declined, completed, error)
- [ ] Tests prove the state machine cannot reach a destructive action without confirmation
