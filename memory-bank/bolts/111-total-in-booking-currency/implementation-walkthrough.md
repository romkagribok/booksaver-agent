---
stage: implement
bolt: 111-total-in-booking-currency
created: 2026-11-10T13:52:31Z
---

# Implementation Walkthrough: total-in-booking-currency

## Summary

The booking's currency is taken from the price area's amount-only lines; Jev chooses the total only
among lines in that currency, each distinct line once, and is told the currency.

## Structure Overview

`booking_currency(area)` and the total options in `JevReservationFacts.__call__`
(`src/booksaver/infrastructure/browser/jev_reservation_facts.py`); adapter `jev-reservation-facts-v5`.

## Completed Work

- `booking_currency`: fullmatch of one money amount per line; one currency or None.
- Total options: lines whose amounts are all in that currency, deduplicated by text; a total in
  another currency never counts; unknown currency keeps every line.
- Question names the reservation's currency; "in the currency they will be charged" removed.

## Key Decisions

Symbol-and-digit rule instead of a Jev currency answer (see Deviations).

## Deviations from Plan

1. Jev `booking_currency` question (first version): on staging it answered EUR for Ayres (0.98) and
   Park Plaza (0.89); two more wordings failed offline. Replaced by the amount-only rule.
2. With only USD lines Jev answered "none": the question's "currency they will be charged" phrase
   and triple-repeated amounts. Wording changed and options deduplicated.

## Dependencies Added

None.

## Developer Notes

Human checkpoints skipped under the standing waiver (CLAUDE.local.md point 4).
