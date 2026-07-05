---
id: 004-savings-detection-notifications
unit: 003-savings-detection-notifications
intent: 001-booksaver-agent-mvp
type: ddd-construction-bolt
status: complete
stories:
  - 001-compare-live-price-to-baseline
  - 002-enforce-pragmatic-equivalence-and-refundability
  - 003-notify-via-email-and-telegram
created: 2026-07-05T00:00:00.000Z
started: 2026-07-05T00:00:00.000Z
completed: "2026-07-05T19:11:45Z"
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
    artifact: adr-011-stdlib-notification-transports.md
  - name: implement
    completed: 2026-07-05T00:00:00.000Z
    artifact: src/booksaver/domain/savings.py + application/savings_pipeline.py + infrastructure/notifications/
  - name: test
    completed: 2026-07-05T00:00:00.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 001-core-local-data
  - 002-core-local-data
  - 003-booking-com-price-monitor
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 2
---

# Bolt: 004-savings-detection-notifications

## Overview

Pure domain logic evaluating successful CheckResults against booking baselines
(equivalence + refundability gate, strict price comparison) plus email and Telegram
notification adapters. No browser automation in this unit.

## Objective

When a scheduled check succeeds: validate the offer is pragmatically equivalent
(same stay, same room, still refundable), compare against the baseline, persist a
SavingsOpportunity when live < baseline, and alert via email and Telegram — each
channel attempted independently.

## Stories Included

- **US-007**: Compare live price to baseline (Must)
- **US-008**: Enforce pragmatic equivalence and refundability (Must)
- **US-009**: Notify via email and Telegram (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ✅ **1. Domain Model**: Complete → ddd-01-domain-model.md
- ✅ **2. Technical Design**: Complete → ddd-02-technical-design.md
- ✅ **3. ADR Analysis**: Complete → adr-011
- ✅ **4. Implement**: Complete → domain/savings.py + savings_pipeline + notifiers
- ✅ **5. Test**: Complete → ddd-03-test-report.md (168/168)

## Dependencies

### Requires
- Bolt 001 (Booking baselines, NotificationSettings, Config)
- Bolt 003 (CheckResult payloads from successful checks)

### Enables
- Unit 4 (guided rebook) consumes SavingsOpportunity records

## Success Criteria

- [ ] Cheaper + equivalent + refundable offers produce a persisted SavingsOpportunity
- [ ] Non-equivalent / non-refundable / equal-or-higher offers are skipped and logged
- [ ] Currency mismatch never produces a false positive
- [ ] Email and Telegram both attempted per opportunity; one failing does not block the other
- [ ] Alerts include booking id, baseline vs live, amount + percent saved, rebook pointer
- [ ] Tests cover the full equivalence/refundability decision matrix
