---
id: 005-guided-rebook
unit: 004-guided-rebook
intent: 001-booksaver-agent-mvp
type: ddd-construction-bolt
status: in-progress
stories:
  - 001-start-guided-rebook-only-after-explicit-intent
  - 002-mandatory-confirmation-before-cancel-or-purchase
  - 003-log-rebook-outcomes-locally
created: 2026-07-05T00:00:00Z
started: 2026-07-05T00:00:00Z
completed: null
current_stage: model
stages_completed: []

# Bolt Dependencies
requires_bolts:
  - 001-core-local-data
  - 002-core-local-data
  - 003-booking-com-price-monitor
  - 004-savings-detection-notifications
enables_bolts: []
requires_units: []
blocks: false

# Complexity Assessment
complexity:
  avg_complexity: 2        # session state machine + confirmation gates; browser reuse
  avg_uncertainty: 2       # Booking.com rebook flow specifics; MVP keeps browser steps guided
  max_dependencies: 3      # SavingsOpportunity, Booking, BrowserSession
  testing_scope: 2         # state machine + confirmation gate matrix + audit log
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

- [ ] **1. Domain Model**: Pending → ddd-01-domain-model.md
- [ ] **2. Technical Design**: Pending → ddd-02-technical-design.md
- [ ] **3. ADR Analysis**: Pending → adr-*.md
- [ ] **4. Implement**: Pending → src/
- [ ] **5. Test**: Pending → ddd-03-test-report.md

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
