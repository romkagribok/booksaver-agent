---
version: jevfacts-21694ab
commit: 21694ab
created: "2026-11-08T19:03:07Z"
status: deployed-verified
recorded: "2026-11-08T19:05:00Z"
---

# Jev reads the booked party, meals and missing dates (intent 034, release A)

## Change

Bolt 105 (US-257): Jev reads adults, children, rooms and nights (nights must match the dates) and the
meal plan with its stated line, in the same two calls as total, refund and room; dates stay code-first
with Jev filling them when code cannot; the code party and meal readers are removed; a hotel link keeps
the property without its query; the stall message names missing facts. Personal label rows and their
values, the confirmation number and long digit runs are removed before anything reaches TypeSafe.

## Artifact and verification

- PR #107, head `fda5619`, merge `21694ab1ea67`. Codex rounds: `9f23fb6` P1 (label values and spaced
  confirmation numbers survived) and P2 (meal class without an agreed line), fixed in `e6c537a`;
  `e6c537a` P2 (numeric dates removed by the long-number filter), fixed in `fda5619`; `fda5619` no
  major issues. `scripts/codex_merge_gate.py 107` passed (exit 0) before the merge.
- Image `booksaver-agent:jevfacts-21694ab` =
  `sha256:c9c7b374c6e198252492a2bf5b286c39233a816afe1f626ccda2920c5fd9fba5`, built from the merge's
  `git archive` on `jevroom-86279b0` with the clean-tree kit Dockerfile; adapter
  `jev-reservation-facts-v4`; 116 modules.
- Quality: 2,597 passed, 1 skipped; Ruff and mypy clean; AI-DLC validators 0 errors.
- Live Jev on seven captured real reservations: party, meals and room equal the previous code
  readings; variants (children, reworded breakfast, missing meal row, unsupported and numeric dates)
  correct. Replay of users 4, 1 and 3 on cloned data: all syncs complete, all upcoming reservations
  unchanged; user 4's sync cost about USD 0.0024.
- Promotion: backup `/opt/booksaver-backups/jevfacts-21694ab-20261108`, healthy, schema 24, public
  health passed, Caddy unchanged, at 2026-11-08T19:03:07Z. Rollback tag
  `booksaver-agent:rollback-pre-jevfacts-21694ab` (no schema change).

## Production read-back

Every user 4 sync from 2026-11-08T20:42Z to 2026-11-09T19:02Z (five) and user 1 sync (four) read
party, meal plan and room for every page (`read_party=7 read_meal_plan=7 read_room_type=7`); all seven
upcoming reservations kept their facts and eligibility. One user 4 page leaves the total and/or refund
terms unread on most syncs; the same happened under `jev-reservation-facts-v3` before this release
(2026-11-07 onwards), and the saved values are kept, so it is not a regression.
