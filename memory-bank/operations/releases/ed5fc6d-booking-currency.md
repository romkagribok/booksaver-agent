---
version: currency-ed5fc6d
commit: ed5fc6d
created: "2026-11-10T13:56:22Z"
status: deployed-verified
recorded: "2026-11-10T23:58:29Z"
---

# The booked total is read in the booking's currency (intent 038)

## Change

Bolt 111 (US-263).
- **Booking currency from the price area:** an amount-only line ("US$147.78", "€ 102") sets the
  booking's currency when every such line agrees. Approximate conversions ("approx. € 132") never
  count.
- **Jev picks the total from lines in that currency only.** Its question names the currency. A Jev
  answer in another currency is discarded. When no amount-only line exists, every price line is
  offered as before.
- Adapter `jev-reservation-facts-v5`. The Jev currency question was dropped after staging (Jev
  answered EUR for two USD bookings). The deviation is recorded in the unit construction log.

## Artifact and verification

- PR #117, head `36d1e93`, merge `ed5fc6d48e28`. Codex reviewed `36d1e93`: no findings.
  `scripts/codex_merge_gate.py 117` passed (exit 0) before the merge.
- Image `booksaver-agent:currency-ed5fc6d` =
  `sha256:64cb558d46746cbf6757bbcab9df02dc535a2f1dbe409ebb1019ff2e8673cbad`. Built from the
  merge's `git archive` on `tripcards-db3207b` with the clean-tree kit Dockerfile; 116 modules.
  The source is identical to the staged head `89c8d84`.
- Quality: 2,572 passed, 1 skipped. Ruff and mypy clean. AI-DLC validation found 0 inconsistencies.
- Staging (kit `currency-20261110`):
  - Offline Jev on five real price areas (Ayres, Aloft, Park Plaza, Best Western, AIRINN), three
    runs each: all correct.
  - Staged replay 13:46–13:51Z (cloned data, no notifications): the user 4 sync was complete. Ayres
    went from EUR 133 to USD 147.78, every other reservation was unchanged, and the Ayres check ran
    in USD.
- Promotion: backup `/opt/booksaver-backups/currency-ed5fc6d-20261110`. Healthy, SQLite integrity,
  schema 24, public health passed, Caddy unchanged at 2026-11-10T13:56:22Z. Rollback tag
  `booksaver-agent:rollback-pre-currency-ed5fc6d`; no schema change.

## Production read-back

User 4's scheduled sync and checks at 18:54Z on 2026-11-10 (running on `minsave-52c1330`, which
contains this change):
- **Sync:** complete; 7 discovered and 5 eligible as before; `read_booked_total=6` of 6 pages.
  The intermittent `unread_booked_total=1` is gone.
- **Ayres:** the monitored booking is now USD 147.78 (it was EUR 133). The 18:54:55Z check priced
  it at USD 144 in the same room. The EUR 132 checks at 06:53Z and 09:47Z stopped.
- **Other bookings:** unchanged currencies and checks:
  - Park Plaza: USD 378 against 344.50.
  - Best Western: USD 512 against 494.92.
  - AIRINN: EUR 157 against 102.
  - Kalipè: no availability.
