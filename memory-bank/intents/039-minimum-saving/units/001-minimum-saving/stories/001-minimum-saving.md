---
id: 001-minimum-saving
unit: 001-minimum-saving
intent: 039-minimum-saving
status: draft
priority: must
created: "2026-11-10T14:50:41Z"
assigned_bolt: 112-minimum-saving
implemented: false
---

# Story: US-264 No alert for a saving under 5 in the booking currency

## User Story

**As a** BookSaver user
**I want** alerts only for savings of at least 5 in my booking's currency
**So that** I am not told to rebook for a euro or a dollar

## Acceptance Criteria

- [ ] **Given** a booked EUR 133 and a live EUR 132, **When** checked, **Then** no opportunity is stored or alerted.
- [ ] **Given** a booked USD 105 and a live USD 100, **When** checked, **Then** an opportunity of USD 5 is stored and alerted.
- [ ] **Given** a saving of USD 4.99, **When** checked, **Then** it is rejected as below the minimum.

## Technical Notes

`MINIMUM_SAVING = Decimal("5")` and `RejectionReason.SAVING_BELOW_MINIMUM` in `domain/savings.py`.

## Dependencies

### Requires
- None

### Enables
- None

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Exactly 5.00 saved | Opportunity |
| Currencies with small units (JPY) | Same rule; accepted limitation |

## Out of Scope

- Re-alerting an unchanged saving on every check.
