---
version: jevbetter-3cdaf88
commit: 3cdaf88
created: "2026-11-10T01:42:19Z"
status: deployed-verified
recorded: "2026-11-10T01:45:00Z"
---

# A cheaper same-or-better room counts as a saving (intent 035, bolt 109)

## Change

Owner, 2026-11-10: "yes it should count as a saving (same or better)". This is bolt 109 (US-261,
ADR-065, amends ADR-064).

- Jev compares every priced room that doesn't carry the booked name with the booked room, for the
  booked guests: same, better or neither. It is asked twice, and both answers must agree at 0.8 or
  more. Same and better rooms are compared on price.
- The alert names the offered room and says whether it is a better room.
- A sure meal, refund or tax class (0.8) counts when Jev names a stating line as its top pick. The
  line no longer needs 0.8 of its own, because duplicate lines split that confidence.
- The image also contains PR #113 (removes `max_bookings_per_user` and the retired-keys list, merge
  `28abf16`). Its own session verifies and records it.

## Artifact and verification

- PR #112, head `517654d`, merge `3cdaf8814526`. Codex found no issues on `c0f0517` or `517654d`.
  `scripts/codex_merge_gate.py 112` passed (exit 0) before the merge.
- Image `booksaver-agent:jevbetter-3cdaf88` =
  `sha256:eea523a101aaf9a9d10f6f9e7a7276b91b24f788040ef7bf2c9aa6697a1982ba`. It was built from the
  merge's `git archive` on `jevprice-003d03f` with the clean-tree kit Dockerfile; 116 modules.
- Quality: 2,560+ tests passed, 1 skipped. Ruff and mypy clean. AI-DLC validation found 0
  inconsistencies.
- Staged replays (kit `jevbetter-20261110`; daemon paused 01:20–01:31Z and 01:33–01:37Z; cloned data,
  no notifications; restored healthy each time):
  - Jev's comparisons were sensible and agreed across both runs. Twin, triple and family rooms were
    neither; balcony, kitchenette and suite rooms were better; uncertain answers (0.3–0.79) were not
    counted.
  - Run 1 showed better rooms' breakfast rates as unknown, because their meal-line confidence was
    split. The line rule was fixed in `517654d`.
  - Run 2: AIRINN priced at EUR 157 for "Standard Double Room with Balcony" (better, breakfast,
    refundable). That is above the EUR 102 paid, so no saving. Ayres priced at USD 132; Park Plaza at
    USD 364 (run 1).
- Promotion: backup `/opt/booksaver-backups/jevbetter-3cdaf88-20261110`. Healthy, schema 24, public
  health passed, Caddy unchanged at 2026-11-10T01:42:19Z. `config.toml` kept. Rollback tag
  `booksaver-agent:rollback-pre-jevbetter-3cdaf88`; no schema change.

## Production read-back

Production checks on 2026-11-10:
- **AIRINN (2026-11-17):** priced EUR 157 at 06:55Z and 09:50Z on a better room ("Standard Double
  Room with Balcony", breakfast, refundable). That is above the EUR 102 paid, so no alert. It had
  never priced before.
- **Park Plaza:** USD 364 on the same-room match.
- **Union Club** (user 1): USD 570 against USD 592.48 paid gave a USD 22.48 saving alert at 11:44Z,
  on an exact room match.
- **Syncs:** 02:32Z, 06:52Z, 09:47Z and 11:43Z all complete, with no stall notices.
