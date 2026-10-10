---
unit: 001-reservation-meal-plan
intent: 027-meal-plan-equivalence
phase: inception
status: stories-defined
unit_type: backend
default_bolt_type: ddd-construction-bolt
created: "2026-10-10T01:49:45Z"
---

# Reservation meal plan

Read, store, and show each reservation's meal plan (requirements 2 to 5). Owns the meal plan
value and its text classifier in the domain layer, the confirmation parser rule, the path from
observed reservation to `account_reservations` and `bookings` (schema v20), and the `/bookings`
line. Does not change offer selection or alerts.
