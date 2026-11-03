---
unit: 002-jev-currency-pin
bolt: 094-jev-currency-pin
stage: model
status: complete
created: 2026-11-03T00:52:47Z
updated: 2026-11-03T00:52:47Z
---

# Static Model - Jev Currency Pin

## Bounded Context

One Jev price execution for one booking.

## Domain Entities

- **Property page**: the offer source. Its displayed currency is set by the URL's
  `selected_currency` and otherwise by the signed-in account's default.

## Value Objects

- **Booked currency**: the currency of the reservation's total. Offers are compared only in it.

## Domain Rules

1. Offers are read from a page requesting the booked currency.
2. A redirect that removes the request is corrected once per check.
3. Offer validation stays the authority: a page in another currency fails with `currency_mismatch`.

## Ubiquitous Language

**Pin**: re-opening the redirected page with the booked currency requested.
