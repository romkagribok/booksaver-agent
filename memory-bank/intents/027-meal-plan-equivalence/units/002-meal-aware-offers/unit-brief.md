---
unit: 002-meal-aware-offers
intent: 027-meal-plan-equivalence
phase: inception
status: stories-defined
unit_type: backend
default_bolt_type: ddd-construction-bolt
created: "2026-10-10T01:49:45Z"
---

# Meal-aware offers

Read each candidate rate's meal plan on every price path that can produce an alert, gate offer
selection on it, and state both meal plans in alerts (requirements 1 and 6 to 10). Owns the
equivalence ADR and the amended repository boundary. Depends on unit 001.
