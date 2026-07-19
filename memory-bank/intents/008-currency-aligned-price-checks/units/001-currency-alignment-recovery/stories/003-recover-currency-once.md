---
id: 003-recover-currency-once
unit: 001-currency-alignment-recovery
intent: 008-currency-aligned-price-checks
status: ready
priority: must
created: 2026-07-19T00:32:13Z
assigned_bolt: 020-currency-alignment-recovery
implemented: false
---

# Story: Recover an Otherwise-Valid Currency Mismatch Once

**Global story ID**: US-059

## User Story

**As a** BookSaver user running checks from a localized VPS
**I want** the monitor to correct Booking.com's display currency automatically
**So that** a valid refundable equivalent offer can still be evaluated

## Acceptance Criteria

- [ ] Recovery begins only when selection contains an otherwise-eligible currency-only mismatch.
- [ ] The monitor applies a deterministic same-site currency preference before spending an LLM call.
- [ ] If deterministic alignment cannot complete or verify, the guarded browser agent may operate the
  visible currency selector under existing action and budget restrictions.
- [ ] The monitor reloads trusted booking context and re-extracts candidates at most once.
- [ ] A recovered same-currency candidate re-enters the unchanged selection and savings pipeline.
- [ ] Recovery never resets wall-clock, LLM-call, or agent-step budgets.

## Technical Notes

- Model the recovery result explicitly with method and diagnostic detail.
- Agent verification must inspect refreshed rendered evidence; agent assertion alone is insufficient.

## Dependencies

### Requires

- US-057 trusted navigation and US-058 currency-only selection evidence.

### Enables

- US-060 terminal failure classification and US-061 pipeline regression coverage.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Deterministic preference succeeds | Re-extract without an LLM call |
| Preference is ignored | One guarded fallback may run, then final verification |
| Check budget expires during alignment | Existing budget failure terminates; no second attempt |
| Refreshed offer becomes unavailable | Normal refreshed selection/failure applies; no retry loop |

## Out of Scope

- Repeated attempts across multiple currencies or an unbounded LLM exploration loop.
