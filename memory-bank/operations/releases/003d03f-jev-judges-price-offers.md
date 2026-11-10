---
version: jevprice-003d03f
commit: 003d03f
created: "2026-11-10T01:07:59Z"
status: deployed-verified
recorded: "2026-11-10T01:10:00Z"
---

# Jev judges the booked room and each rate's meals, refund and taxes (intent 035, release B)

## Change

Bolt 106 (US-258, ADR-064). When no priced room carries the booked name, Jev names which priced room
is the booked room type. It sees every priced room on the page, is asked twice, and both answers must
agree at 0.8 or more. Jev also classifies each rate's meals, and its refund and tax answers count when
it names the stating line at 0.8. The English meal word lists and the refund and tax regexes are
removed. A matching Booking.com link proves the hotel without exact name equality. Totals keep their
code grounding. The image also contains PR #108 (per-user Jev daily cap; check limit default 150,
merge `336f23e`). That PR's verification is recorded separately by its own session.

## Artifact and verification

- PR #110, head `400d8a0`, merge `003d03f22662`. Codex: `ee84a31` no findings and `400d8a0` no
  findings. `scripts/codex_merge_gate.py 110` passed (exit 0) before the merge.
- Image `booksaver-agent:jevprice-003d03f` =
  `sha256:c644867e213d56ef1b7cf7e3862642898686fd60cd7ec93f14b1b6b020b6d5e9`. It was built from the
  merge's `git archive` on `jevfacts-21694ab` with the clean-tree kit Dockerfile. 116 modules;
  `classify_meal_text` is absent and the per-user cap is present.
- Quality: 2,555 passed, 1 skipped. Ruff and mypy are clean. AI-DLC validation found 0 inconsistencies.
- Staged live replay (kit `jevprice-20261110`). The daemon was paused 00:46–01:01Z, the data was
  cloned and no notifications were sent; production was restored healthy on the same image.
  - Park Plaza priced at USD 364 through Jev's room match ("Deluxe Queen Bed" = "Deluxe Queen Bed
    Room", 0.84 / 0.82).
  - AIRINN (Nov 17): none, twice (0.88 / 0.87). No plain Standard Double is on sale; only "…with
    Balcony", Business and Comfort rooms.
  - Ayres USD 148 (breakfast), Best Western 512 and Union Club 570 were priced as before. Kalipè still
    shows no availability.
- Offline Jev meal wording check: 27 wordings. The first run gave one overclaim (a bare "Breakfast"
  line); a hint was added in `400d8a0`, and the second run gave 0 overclaims.
- Promotion: backup `/opt/booksaver-backups/jevprice-003d03f-20261110`. Healthy, schema 24, public
  health passed and Caddy unchanged at 2026-11-10T01:07:59Z. `config.toml` was kept
  (`max_checks_per_user_per_day = 150`). Rollback tag `booksaver-agent:rollback-pre-jevprice-003d03f`;
  there is no schema change.

## Production read-back

Production checks on 2026-11-10 (by then running `jevbetter-3cdaf88`, which contains this release):
- **Park Plaza Lodge:** priced USD 364 at 06:53Z and 09:48Z through Jev's room match. It had failed
  with "No matching room type found" on 2026-11-09.
- **Unchanged:** Best Western USD 512, Union Club USD 570, Kalipè no availability.
- **Ayres Hotel Vista Carlsbad:** priced in EUR and alerted a EUR 1 "saving" twice. The cause is the
  reservation reader saving Booking.com's "approx. €" estimate instead of US$147.78, not this
  release; it is fixed by intent 038.
