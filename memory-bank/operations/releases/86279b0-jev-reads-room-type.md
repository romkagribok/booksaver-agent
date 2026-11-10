---
version: jevroom-86279b0
commit: 86279b0
created: "2026-11-08T03:05:13Z"
status: deployed-verified
recorded: "2026-11-08T03:10:00Z"
---

# Jev reads the booked room type; agreed totals count (intent 033)

## Change

Bolt 104 (US-256): Jev reads the room type from the lines under "Your room details" before the guest
row (both calls agree at 0.5 or more); the layout-specific room parser is deleted; an agreed total
that passes the code check is accepted with no confidence floor; meals are read for any single-room
party; a room mismatch says "No matching room type found".

## Artifact and verification

- PR #106, head `7993db2`, merge `86279b0f079b`. Codex found one P1 on `857cecd` (room options
  included guest name, confirmation number, PIN and email); fixed in `7993db2`, which Codex reviewed
  with no major issues. `scripts/codex_merge_gate.py 106` passed (exit 0) before the merge.
- Image `booksaver-agent:jevroom-86279b0` =
  `sha256:5ee1a1ae515b2f242d0c1f26ab6942988d5195103fca12a45011509b53dbd68f`, built from the merge's
  `git archive` on `noavail-39a666b` with the clean-tree kit Dockerfile; 116 modules, `_room_fact`
  absent.
- Quality: 2,617 passed, 1 skipped; Ruff and mypy clean; AI-DLC validators 0 errors.
- Replay of users 4 and 1 on cloned data (kit `jevroom-20261108`, last restored healthy at
  02:59:37Z): Park Plaza Lodge eligible (Deluxe Queen Bed, USD 344.50, refundable until 2026-11-12,
  meals none); the other seven upcoming reservations unchanged; room confidence 0.97 to 1.0.
- Promotion: backup `/opt/booksaver-backups/jevroom-86279b0-20261108`, healthy, schema 24, public
  health passed, Caddy unchanged, at 2026-11-08T03:05:13Z. Rollback tag
  `booksaver-agent:rollback-pre-jevroom-86279b0` (no schema change).

## Production read-back

The dad's sync at 2026-11-08T13:01Z read Park Plaza Lodge's room type ("Deluxe Queen Bed") and
agreed total (USD 344.50), and the reservation became eligible. Its first check at 13:01:35Z priced
USD 364, and again at 20:43Z. The 2026-11-09 checks then failed on the room-name difference ("Deluxe
Queen Room" offer); release B (`003d03f`) fixed that.
