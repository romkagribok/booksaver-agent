---
stage: plan
bolt: 112-minimum-saving
created: 2026-11-10T14:50:41Z
---

# Implementation Plan

## Objective

A saving under 5 units of the booking currency is not an opportunity.

## Deliverables

- `domain/savings.py`: `MINIMUM_SAVING = Decimal("5")`, `RejectionReason.SAVING_BELOW_MINIMUM`,
  checked in `detect_savings` after the lower-price check.
- Unit tests in `tests/unit/savings/test_savings_detection.py`.

## Dependencies

None.

## Technical Approach

Compare `baseline - live` with the minimum in the same currency (already enforced equal).

## Acceptance Criteria

See US-264.
