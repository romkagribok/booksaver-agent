---
stage: test
bolt: 108-remove-booking-cap
created: 2026-11-10T01:17:09Z
---

# Test Walkthrough

- `LimitsSettings` has no booking cap; a config setting `max_bookings_per_user` (even 0) loads; the
  production-shaped config with old `[agent]`, routing and limits keys loads; the retired-model values
  test still loads them (warning assertions removed with the warning).
- Full suite 2,555 passed, 1 skipped; Ruff and mypy clean (re-run after the deletion: same).
