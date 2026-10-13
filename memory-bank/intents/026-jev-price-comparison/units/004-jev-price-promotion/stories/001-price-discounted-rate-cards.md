---
id: 001-price-discounted-rate-cards
unit: 004-jev-price-promotion
intent: 026-jev-price-comparison
status: complete
priority: must
created: "2026-10-10T01:45:00Z"
assigned_bolt: 089-jev-price-promotion
implemented: true
---

# US-216: Price member-discounted rate cards

## User story

As a booking owner whose room has a member discount, I want Jev to read the discounted price, so
my price check and savings alerts keep working when Jev is the only method.

## Assigned requirement

FR-14.

## Background

In 56 paired checks one booking never verified under Jev (0 of 18) while the existing method
verified it 5 times and sent 5 savings alerts. Jev priced 12 of that hotel's 16 rates: exactly the
booked room's four were missing. The verified price is 10% below the signed-out rate, so those
cards most likely show an original and a current price. The signed-in page was not observed.

## Acceptance criteria

- [ ] Given a rate card with an original and a current price in any of the labelled layouts
  (separate labelled amounts, labels then amounts, one combined line, original not struck out),
  when Jev chooses, then only the current whole-stay price is grounded as the total.
- [ ] Given Jev chooses the original price, when grounding, then the rate stays unpriced.
- [ ] Given two different unlabelled amounts and no label, when grounding, then the rate stays
  unpriced (`ambiguous`) rather than trusting a guess.
- [ ] Given undiscounted cards with a labelled price, when grounding, then they are still priced.
- [ ] Given any amount that is a nightly, original, tax/fee/deposit, saving or per-person figure,
  or that equals the card's nightly amount on a stay longer than one night, when chosen, then it
  is never grounded as the total.
- [ ] Given an unlabelled amount on a stay longer than one night, when chosen, then the rate stays
  unpriced.
- [ ] Given a struck-through price whose line-through is set on an ancestor element, when the page
  is read, then it is not offered as a candidate.
- [ ] Given the real affected booking in production, when a scheduled check runs with both methods,
  then Jev verifies it or its diagnostic states why each rate was unpriced.

## Out of scope

Computing taxes or discounts in code; any layout the diagnostics have not shown.
