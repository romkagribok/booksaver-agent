---
bolt: 035-booking-account-sync-core
completed: 2026-07-27T17:01:58Z
---

# Test Report

- Fresh schema and historical v1/v4/v6/v8/v9/v10 upgrade paths pass.
- Migration assertions confirm legacy booking/check state is removed and users, invites, keys, and
  access records survive.
- Complete, partial, failed, absent, per-user identity, projection, and idempotent reopen behavior
  pass.
- Full repository: **959 passed**; Ruff and mypy clean.
