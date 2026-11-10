---
version: jevroom-86279b0
commit: 86279b0
created: "2026-11-08T03:05:13Z"
status: deployed-verified
recorded: "2026-11-10T00:52:50Z"
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

Read 2026-11-10T00:46:02Z to 00:49:37Z. Method: read-only, through the specs.md operations agent's verify step: `ssh booksaver`, `docker ps/inspect/events/logs`, and the live database opened read-only from the host volume (`mode=ro`); the app's store was not opened and nothing was stopped, restarted, written or replayed.

- Park Plaza Lodge (0e0f017f, booking 4c1e8d7f, user 4): before (pre-release backup) room, total and meals empty and `ineligible`; user 4's first sync on this image (2026-11-08T13:01:10Z) set room "Deluxe Queen Bed", total USD 344.50 (source `jev`), meals none, refundable until 2026-11-12, `eligible`. A price check ran 25 s later (USD 364, no saving); values unchanged at 2026-11-09T19:02:34Z.
- Other reservations: every upcoming reservation of users 1 and 4 keeps the same room type across the pre-release backup, the next backup and the live database.
- "No matching room type found" seen in production (AIRINN from 2026-11-08T13:03Z; Park Plaza from 2026-11-09, where the page offered 1 room instead of 2, an inventory change).
- Not observed: room confidence values (0.97 to 1.0 on staging) are not stored in production.
- Caveat, logs: daemon logs since the promotion no longer exist. Another session recreated the `booksaver` container at 2026-11-10T00:41:38Z (Docker json-file logs go with the container), so `docker logs` starts at 00:41:54Z with five clean startup lines. "No errors" rests on database outcomes (`booking_sync_runs`, `check_history`, `jev_price_runs`, `scheduled_check_slots`, `monitoring_stall_notices`) and the later promotion health logs, not on a log scan.
- Caveat, production state at read-back: at 2026-11-10T00:49Z the `booksaver` daemon was `Exited (0)`, paused at 00:46:37Z by a concurrent session's `jevprice-20261110` staging kit (its marker says its `run.sh` restores it). Not caused by this release; its restore was not observed in this read-back.

Verdict: passed.
