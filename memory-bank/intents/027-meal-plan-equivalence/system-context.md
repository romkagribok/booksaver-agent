---
intent: 027-meal-plan-equivalence
phase: inception
status: context-defined
created: "2026-10-10T01:49:45Z"
updated: "2026-10-10T07:49:45Z"
---

# Meal plan equivalence - System Context

## System Overview

The reservation's meal plan enters through account synchronization: the code-owned confirmation
parser reads it from the reservation page text that the grouped inventory reader already captures,
and it travels with the other observed facts into `account_reservations` and the derived `bookings`
projection. `/bookings` renders it from the stored reservation. Each price method reports a
candidate rate's meal plan with the text it relied on; offer selection in the domain layer is the
single place that compares it with the reservation's. The savings alert reads the result.

## Context Diagram

```text
Booking.com reservation page -> grouped inventory reader -> confirmation parser (meal plan)
        -> observed reservation -> account_reservations -> bookings projection -> /bookings
Booking.com property page -> price method (rate meal plan) -> select_offer (gate) -> savings alert
```

## External Integrations

None added. Booking.com is read through the existing authenticated browser session.

## High-Level Constraints

- Provider-submitted reservation facts cannot set a meal plan.
- No page text is stored; only the classified value and one bounded line of rate wording.
- No new secret, service or dependency.

## Key NFR Goals

Fail closed toward `unknown`; never round wording to a value; additive migration.
