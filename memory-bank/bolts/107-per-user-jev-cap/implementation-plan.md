---
stage: plan
bolt: 107-per-user-jev-cap
created: 2026-11-10T00:46:00Z
---

# Implementation Plan

- `SqliteJevPriceRunRepository.cost_since` and `SqlitePriceComparisonRepository.jev_cost_since` take a
  required `user_id` and sum only that user's rows.
- `JevPrimaryPriceExecutor._remaining_daily_nano_usd` uses `request.owner_user_id`.
- `remaining_daily_nano_usd` (reservation facts) takes `user_id`; the facts-assistant factory becomes
  `Callable[[int], ...]` and `LocalBrowserUseInventoryExecutor` calls it with
  `request.owner_user_id`.
- Wording: "shared" cap -> per user in docstrings, the startup log, `config.toml.example`.
- `LimitsSettings.max_checks_per_user_per_day` default 48 -> 150; example config and `init` template.
- Tests: another user's spend does not refuse a run; own spend does; facts budget per user; default 150.
