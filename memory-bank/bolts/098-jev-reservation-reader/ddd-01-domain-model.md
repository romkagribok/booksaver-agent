---
unit: 001-jev-reservation-reader
bolt: 098-jev-reservation-reader
stage: model
status: complete
created: 2026-11-04T15:35:28Z
updated: 2026-11-04T15:35:28Z
---

# Static Model - Jev Reservation Reader

## Bounded Context

Reading one confirmation page during account sync; reconciliation consumes the facts.

## Domain Entities

- **Confirmation reading**: code facts (identity, stay, room, guests, meal plan) plus Jev facts
  (booked total, refund terms).

## Value Objects

- **Agreed answer**: the same choice in two Jev runs, each above its confidence bar.
- **Checked total**: one amount, the largest in its currency in the price area.
- **Checked deadline**: a date in the chosen line, or "within ..." with calendar months, 14 hours
  ahead and not after check-in.

## Domain Rules

1. Jev is the only reader of total and refund terms; checks hold for any layout.
2. An agreed, checked total is page-verified and may replace a saved one.
3. An unread fact keeps the saved value; a new reservation stays unconfirmed and the stall message
   covers it.
