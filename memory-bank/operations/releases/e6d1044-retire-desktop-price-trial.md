---
version: retiretrial-e6d1044
commit: e6d1044
created: "2026-11-18T13:12:35Z"
status: deployed-verified
recorded: "2026-11-18T13:20:24Z"
---

# Desktop price trial retired (intent 041, bolt 115, GitHub issue #7)

## Change

- **Code:** everything PR #123 added is removed: the reading loop after a scheduled slot, the
  desktop browser profile, the desktop room-table reader, the trial executor and the
  `[desktop_trial]` setting. `src/` equals the tree before the trial except for the schema.
- **Schema 26:** a migration drops `desktop_trial_readings` (53 rows). The trial's 53
  `jev_price_runs` rows stay as spend history.
- **Config:** the `[desktop_trial]` section and its two comment lines are removed from
  `/opt/booksaver-agent/config.toml` in the same promotion.
- Owner, 2026-11-17: "Retire tomorrow at 8am and close the issue".

## Why

The evaluation (in `34d89a8-desktop-price-trial.md`): 53 pairs, 27 with a verified price on both
sides, all 27 equal; desktop was never cheaper.

## Artifact and verification

- PR #127, head `fd3fd69`, merge `e6d104486ac6`. Codex reviewed `fd3fd69`: no major issues.
  `scripts/codex_merge_gate.py 127` passed (exit 0) before the merge.
- Image `booksaver-agent:retiretrial-e6d1044` =
  `sha256:73fe9d8f1e8c9e0517c2d4d96d761ad86fe657b807812fbd46fa8de28ac66f7c`, built
  2026-11-18T13:10:07Z in kit `/opt/booksaver-releases/retiretrial-20261118` with `Dockerfile.kit`
  on `booksaver-agent:desktoptrial-34d89a8`, from the `git archive` of the candidate `fd3fd69`.
  The promotion script proved the merge has the same `src`, `scripts`, `pyproject.toml` and
  `requirements.lock` as the candidate.
- Quality: 2,628 passed, 1 skipped. Ruff and mypy clean. AI-DLC validation found 0 inconsistencies.
- Development (no network): 117 modules installed, the same number as in the source; schema 26;
  no `desktop_trial` module or file in the image; `pip check` clean.
- Staging (no network, a `sqlite3` backup copy of the live database, the candidate image):
  - Schema 25 with 53 trial rows opened at 26 without the table; a second open changed nothing.
  - Integrity and foreign keys passed; the row counts of the 22 other tables were unchanged; the
    53 trial rows in `jev_price_runs` were kept.
  - The production config with its `[desktop_trial]` section and the same file without it load
    as the same configuration.
  - Rollback: the previous image opened the migrated copy, recreated the table empty and left
    every other table unchanged.
- Promotion (`promote-e6d1044.sh`, log `promotion.log`): no check was running; daemon stopped;
  backup `/opt/booksaver-backups/retiretrial-e6d1044-20261118` (data, config, environment;
  checksum verified; 53 trial readings in it); config section removed (six lines, nothing
  added) and validated in the new image; healthy on the new image with restart count 0;
  integrity, foreign keys, schema 26 and no trial table; public health passed; Caddy unchanged;
  finished 2026-11-18T13:12:35Z.
- Rollback: `booksaver-agent:rollback-pre-retiretrial-e6d1044` and the backed-up `config.toml`.
  The previous image recreates the table empty; the readings come back only from the backup.
- Human checkpoints skipped under the owner's standing waiver.

## Production read-back

Read on 2026-11-18T13:19:59Z, read-only, through the operations agent: user 1's slot planned for
13:17:47Z, the first on the new image, ran 13:17:47Z to 13:19:51Z and completed.

- The reservation sync ran and read the booking's facts (`jev-reservation-facts-v5`, observed).
- The mobile price check ran (`jev-price-v3`) and read the property page: no availability for the
  booked dates, stored as `no_equivalent_offer`. That is the hotel being sold out, as on every
  check since 2026-11-17, not the release.
- No desktop run followed it: no `jev-price-desktop-trial` row, and `desktop_trial_readings` does
  not exist. Schema 26. No traceback and no "no such table" in the log since the promotion.
- Container healthy, restart count 0.
- Not yet seen on the new image: a check that ends in a price. User 1's only booking is sold out;
  user 4's next slot (14:22:10Z) has the one booking that still prices. The price path is the
  code that ran before the trial.
