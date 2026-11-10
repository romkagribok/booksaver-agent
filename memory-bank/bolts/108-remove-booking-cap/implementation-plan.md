---
stage: plan
bolt: 108-remove-booking-cap
created: 2026-11-10T01:14:14Z
---

# Implementation Plan

- `LimitsSettings`: drop `max_bookings_per_user` and its validation; docstring no longer mentions a booking cap.
- `load_config`: stop reading it. (Amended 2026-11-10T01:22:48Z at the owner's request: delete `_IGNORED_KEYS`, `_ignored_keys` and the
  startup warning instead of adding to them; unknown keys are already ignored.)
- Tests: limits defaults/overrides without it; production-shaped config still loads and the warning names
  `limits.max_bookings_per_user`.
- Deploy: also delete the line from production `config.toml` (backup first).
