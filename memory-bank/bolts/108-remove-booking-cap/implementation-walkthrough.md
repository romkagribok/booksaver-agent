---
stage: implement
bolt: 108-remove-booking-cap
created: 2026-11-10T01:17:09Z
---

# Implementation Walkthrough

- `LimitsSettings`: `max_bookings_per_user` field and its validation removed; docstring now describes
  only the check ceiling and message rate limit.
- `load_config`: no longer reads it. `_IGNORED_KEYS`, `_ignored_keys` and the "no longer have any
  effect" warning are deleted (the owner called the list bloat); unknown keys were already ignored, so
  old files, production's included, still load. README and `config.toml.example` wording updated.
