---
version: jevprice-003d03f
commit: 336f23e
created: "2026-11-10T01:07:59Z"
status: deployed-verified
recorded: "2026-11-10T01:08:43Z"
---

# Jev daily cap per user; check limit default 150 (intent 036)

## Change

Bolt 107 (US-259): the USD 0.25 Jev daily cap is measured per user (price runs, reservation-facts
runs, historical comparison arms) instead of one total shared by all users; the code default for
`max_checks_per_user_per_day` is 150. Production config already had 150 (config-only change at
2026-11-10T00:41Z, `config-checks150-per-user-check-limit.md`).

## Artifact and verification

- PR #108, merge `336f23e`; Codex clean with no findings on `c17f9c9`; `codex_merge_gate.py 108`
  passed. Quality: 2,599 passed, 1 skipped; Ruff and mypy clean.
- Shipped inside release B's image, not separately: `booksaver-agent:jevprice-003d03f` =
  `sha256:c644867e213d56ef1b7cf7e3862642898686fd60cd7ec93f14b1b6b020b6d5e9`, built from main merge
  `003d03f` (PR #110), which contains `336f23e`; promoted 2026-11-10T01:07:59Z by the release B
  session (backup `/opt/booksaver-backups/jevprice-003d03f-20261110`, rollback tag
  `rollback-pre-jevprice-003d03f`). Promotion evidence is in release B's record.

## Production read-back

2026-11-10T01:08Z, read-only, on a `sqlite3.backup` copy of the live database:
- Container running healthy on `c644867e`, 0 restarts; deployed checkout has `336f23e`.
- Installed source: `cost_since` and `remaining_daily_nano_usd` take `user_id`; the price executor
  passes `owner_user_id`; `LimitsSettings` default 150.
- Startup log: `Jev is the price method model=jev-1.13.0 daily_cap_per_user_nano_usd=250000000`.
- `booksaver config show`: `limits.max_checks_per_user/day: 150`; config `max_daily_cost_usd = "0.25"`.
- Users 1, 3 and 4 each have USD 0.25 remaining (no Jev spend yet on the new UTC day), so isolation
  between users is shown by unit tests, not yet by live spend.
