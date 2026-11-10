---
version: config-checks150
commit: 21694ab
created: "2026-11-10T00:41:37Z"
status: deployed-verified
recorded: "2026-11-10T00:48:47Z"
---

# Per-user check limit 12 -> 150 (config only, intent 036)

## Change

Production `/opt/booksaver-agent/config.toml` `[limits] max_checks_per_user_per_day` 12 -> 150.
Image unchanged (`booksaver-agent:latest`). Owner: "change the checks to 150".

## Why

On 2026-11-09 user 4 had five active bookings at three checks a day (15) against 12; the 19:02Z slot
skipped three bookings with `user_check_limit_reached` and the daily-limit notice was sent.

## Artifact and verification

- Backup `/opt/booksaver-agent/config.toml.pre-checks150-20261110T004137Z`; diff is the one line.
- Peer session told before the restart. `docker compose up -d --force-recreate booksaver` at about
  00:41Z; healthy after 20 s; `booksaver config show` reports `limits.max_checks_per_user/day: 150`.
- The in-memory daily counter reset on restart (UTC day had already rolled over).
- Rollback: restore the backup and recreate.
