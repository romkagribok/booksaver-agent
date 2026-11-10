---
intent: 039-minimum-saving
phase: construction
status: construction
created: "2026-11-10T14:50:41Z"
updated: "2026-11-10T14:50:41Z"
---

# Requirements: A saving alert needs at least 5 in the booking's currency

## Intent Overview

On 2026-11-10 a EUR 1 (0.75 %) saving was alerted twice for one booking. The owner decided: "Let's
make a minimum saving of 5 currency of the booking (like 5$ or 5€)". A lower live price that saves
less than 5 units of the booking's currency is not a savings opportunity: no alert, no stored
opportunity.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| No alerts for trivial savings | No opportunity below 5 in the booking currency | Must |
| Real savings still alert | A saving of 5 or more is stored and alerted as today | Must |

---

## Functional Requirements

### FR-1: Minimum saving of 5 in the booking currency
- **Description**: `detect_savings` returns a new rejection, "saving below minimum", when the
  saving (booked minus live, same currency) is below 5 units of the booking's currency.
- **Acceptance Criteria**: EUR 1 and USD 4.99 savings are rejected; USD 5.00 and EUR 22.48 are
  opportunities; the pipeline logs the rejection like other "no savings" reasons.
- **Priority**: Must
- **Related Stories**: US-264

---

## Non-Functional Requirements

### Reliability
| Requirement | Metric | Target |
|-------------|--------|--------|
| No schema or config change | Migrations, config keys | None |

---

## Constraints

### Technical Constraints
- The same number (5) in every currency, as the owner asked; currencies with small units (JPY, HUF)
  get a low threshold in practice. Not configurable until needed.

### Business Constraints
- Owner decision in the request; standing waiver for human checkpoints (CLAUDE.local.md point 4).

---

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| Bookings are in currencies where 5 units is meaningful | Small-unit currencies alert for tiny savings | Revisit if such a booking appears |

---

## Open Questions

| Question | Owner | Due Date | Resolution |
|----------|-------|----------|------------|
| Re-alerting the same saving on every check | Owner | — | Asked 2026-11-10; not answered, not in this intent |
