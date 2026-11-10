---
stage: test
bolt: 107-per-user-jev-cap
created: 2026-11-10T00:48:47Z
---

# Test Walkthrough

- New: another user's spend above the cap leaves this user's price check its full cap; reservation-facts
  budget is each user's own (user 1 full, user 2 cap minus own spend); `cost_since` for another user is
  0. Existing: own spend refuses with `budget_exhausted` and no provider call; unreadable ledger fails
  closed; UTC-day reset. Default `max_checks_per_user_per_day` asserts 150.
- Full suite 2,599 passed, 1 skipped; Ruff and mypy clean.
- Not separately tested: the `jev_cost_since` user filter (historical comparison arms; comparison is
  disabled in production) and the inventory executor passing the user id (checked by mypy).
