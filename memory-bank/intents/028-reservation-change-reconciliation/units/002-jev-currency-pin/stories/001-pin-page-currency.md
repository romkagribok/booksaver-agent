---
id: 001-pin-page-currency
unit: 002-jev-currency-pin
intent: 028-reservation-change-reconciliation
status: draft
priority: must
created: "2026-11-02T20:51:19Z"
assigned_bolt: 094-jev-currency-pin
implemented: false
---

# US-229: Keep the Jev page in the booked currency

## User story

As a BookSaver user, I want prices compared in my booked currency, so that a redirect does not fail every check.

## Assigned requirement

FR-6.

## Acceptance criteria

- [ ] Given a redirect that dropped `selected_currency`, when Jev enters the page, then it re-opens the redirected URL once with the booking's currency before reading offers.
- [ ] Given a page that kept the parameter, when Jev enters, then no extra load happens.
- [ ] Given the re-open, when it lands, then the safety invariant is re-checked.
- [ ] Given an error-page reload after the re-open, when it reloads, then the currency is kept.
- [ ] Given a page still in another currency, when offers are validated, then the check fails with `currency_mismatch`.
- [ ] Given the owner's session on staging, when one Jev check runs, then offers are in USD.

## Out of scope

The dormant Claude price methods.
