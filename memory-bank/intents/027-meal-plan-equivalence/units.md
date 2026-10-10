---
intent: 027-meal-plan-equivalence
created: "2026-10-10T01:49:45Z"
---

# Units

- `001-reservation-meal-plan`: bolt `089-reservation-meal-plan`, stories US-216 and US-217. No
  dependency on the other unit.
- `002-meal-aware-offers`: bolt `090-meal-aware-offers`, stories US-218 to US-221. Depends on unit
  001's stored meal plan and on production readings from its release.
