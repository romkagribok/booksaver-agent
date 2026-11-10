---
intent: 038-booking-currency
phase: construction
status: construction
created: "2026-11-10T13:26:27Z"
updated: "2026-11-10T13:26:27Z"
---

# Requirements: Bookings are stored and checked in the currency they were made in

## Intent Overview

The owner's father reported on 2026-11-10 that his US-dollar booking near Los Angeles (Ayres Hotel
Vista Carlsbad) was handled in euros. His confirmation page shows "Price / approx. € 132 /
US$147.78": the booking is US$147.78 and the euro figure is a display estimate. Jev chose the
"approx. €" line as the booked total, both lines pass the largest-amount check in their own
currency, so the reservation was saved as EUR 133, every price check pinned euros, and a EUR 1
(0.75 %) "saving" from exchange-rate drift was alerted twice (06:53Z and 09:47Z). Park Plaza and
Best Western show the same layout and were read correctly in USD. Price checks already run in the
saved currency and reject offers in another currency; the fault is the saved currency.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Every booking is saved in the currency it was made in | Ayres reads US$147.78 on the next sync; the other six keep their currency | Must |
| No savings alert from exchange-rate drift | Ayres' checks run in USD; no EUR alert for it | Must |

---

## Functional Requirements

### FR-1: Jev states the booking's currency
- **Description**: In the same two calls as the total, Jev answers in which currency the booking is
  priced and paid, choosing among the currencies shown in the price area. Both answers must agree.
- **Acceptance Criteria**: Ayres, Park Plaza, Best Western and Aloft answer USD; AIRINN and Kalipè
  answer EUR; disagreement leaves the currency unknown.
- **Priority**: Must
- **Related Stories**: US-263

### FR-2: The booked total is in the booking's currency
- **Description**: Jev's total counts only when its currency equals the agreed booking currency;
  the total question also says an approximate amount converted for display is never the total.
- **Acceptance Criteria**: "approx. € 132" next to "US$147.78" is never saved as the total; a
  total in another currency than the agreed one leaves the total unread (saved total kept).
- **Priority**: Must
- **Related Stories**: US-263

### FR-3: Saved bookings are corrected by the next sync
- **Description**: The corrected total and currency replace the saved ones through the existing
  page-verified path (ADR-061), so price checks of that booking run in the booking's currency.
- **Acceptance Criteria**: On staging, Ayres becomes USD 147.78 and its price check runs in USD.
- **Priority**: Must
- **Related Stories**: US-263

---

## Non-Functional Requirements

### Reliability
| Requirement | Metric | Target |
|-------------|--------|--------|
| No extra Jev calls | Calls per upcoming page | Unchanged (two) |

### Security
| Requirement | Standard | Notes |
|-------------|----------|-------|
| Data sent to TypeSafe | Existing redaction | Only currency codes of amounts already sent |

---

## Constraints

### Technical Constraints
- Price checks keep using the saved currency (`TrustedPriceQuery.currency`); no conversion.

### Business Constraints
- Owner go-ahead in the request ("Can we enforce the checks in currency in which the booking was
  made?"); standing waiver for human checkpoints (CLAUDE.local.md point 4).

---

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| The non-approximate amount is the booking currency when two are shown | A booking truly paid in the display currency is read in the property currency | Jev decides from the whole price area and payment lines, not a rule |

---

## Open Questions

| Question | Owner | Due Date | Resolution |
|----------|-------|----------|------------|
| Repeated identical savings alerts and very small savings | Owner | — | Reported as findings; not in this intent |
