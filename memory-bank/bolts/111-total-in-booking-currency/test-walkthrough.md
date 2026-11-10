---
stage: test
bolt: 111-total-in-booking-currency
created: 2026-11-10T13:52:31Z
---

# Test Report: total-in-booking-currency

- Unit: 2,572 passed, 1 skipped; ruff, mypy, AI-DLC validation clean. Tests cover the Ayres layout
  (estimate never offered, USD total read), the amount-only rule (EUR, USD, unknown cases).
- Capture (kit `currency-20261110`, 13:20–13:24Z): Ayres shows "approx. € 132 / US$147.78".
- Offline on five real price areas (Ayres, Aloft, Park Plaza, Best Western, AIRINN), three runs each:
  all correct (USD 147.78, 150.89, 344.50, 494.92; EUR 122).
- Staged replay 13:46–13:51Z (cloned data, no notifications): user 4 sync complete; Ayres EUR 133 ->
  USD 147.78 on the reservation and the monitored booking; every other reservation unchanged; Ayres
  price check succeeded in USD (live USD 148, no saving).
