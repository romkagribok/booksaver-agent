---
stage: implement
bolt: 107-per-user-jev-cap
created: 2026-11-10T00:48:47Z
---

# Implementation Walkthrough

- `SqliteJevPriceRunRepository.cost_since(since, user_id)` and
  `SqlitePriceComparisonRepository.jev_cost_since(since, user_id)` filter by `user_id` (required, so no
  caller can sum everyone by accident).
- `JevPrimaryPriceExecutor` measures the cap against `request.owner_user_id`'s spend.
- `remaining_daily_nano_usd(db, settings, now, user_id)`; the facts-assistant factory now takes the user
  id and `LocalBrowserUseInventoryExecutor` passes `request.owner_user_id`.
- "Shared" wording removed from docstrings; startup log key `daily_cap_per_user_nano_usd`;
  `config.toml.example` says per user per UTC day.
- `LimitsSettings.max_checks_per_user_per_day` default 150; example config and `init` template 150.
- Unreadable ledger still returns 0 (refused), unchanged.
