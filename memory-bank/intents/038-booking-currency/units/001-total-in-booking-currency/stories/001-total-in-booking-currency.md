---
id: 001-total-in-booking-currency
unit: 001-total-in-booking-currency
intent: 038-booking-currency
status: draft
priority: must
created: "2026-11-10T13:26:27Z"
assigned_bolt: 111-total-in-booking-currency
implemented: false
---

# Story: US-263 The booked total is read in the booking's currency

## User Story

**As a** BookSaver user with a booking abroad
**I want** my booking saved and checked in the currency I booked in
**So that** I never get a "saving" that is only an exchange-rate change

## Acceptance Criteria

- [ ] **Given** "approx. € 132" and "US$147.78", **When** synced, **Then** the total is USD 147.78.
- [ ] **Given** a total in another currency than the amount-only lines, **When** synced, **Then** it is never offered or saved.
- [ ] **Given** no amount-only line, **When** synced, **Then** every price line is offered as today.
- [ ] **Given** a single-currency page (AIRINN, EUR), **When** synced, **Then** it is read as before.
- [ ] **Given** the real pages on staging, **When** synced, **Then** Ayres becomes USD 147.78, the others keep their totals, and Ayres' check runs in USD.

## Technical Notes

`booking_currency` question with options from the currencies in the price area; `check_total`
gains the agreed currency.

## Dependencies

### Requires
- None

### Enables
- None

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Only one currency on the page | That currency; unchanged behaviour |
| Jev unsure of the currency | Total unread; saved total kept |

## Out of Scope

- Repeated identical savings alerts and a minimum saving (reported to the owner).
