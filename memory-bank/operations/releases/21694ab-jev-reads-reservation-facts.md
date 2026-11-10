---
version: jevfacts-21694ab
commit: 21694ab
created: "2026-11-08T19:03:07Z"
status: deployed-verified
recorded: "2026-11-10T00:52:50Z"
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

Read 2026-11-10T00:46:02Z to 00:49:37Z. Method: read-only, through the specs.md operations agent's verify step: `ssh booksaver`, `docker ps/inspect/events/logs`, and the live database opened read-only from the host volume (`mode=ro`); the app's store was not opened and nothing was stopped, restarted, written or replayed.

- Adapter `jev-reservation-facts-v4`: 9 runs from 2026-11-08T20:42:46Z, all `observed`; user 4 about USD 0.0029 per sync (staging estimate 0.0024), user 1 USD 0.00153 in total.
- Facts kept: for all 7 upcoming reservations of users 1 and 4 (290994ac Union Club; f97c3bf1, d3c66ea3 AIRINN; 5347d701 Aloft; f2e1a76b Best Western; 0e0f017f Park Plaza; 73eb382a Kalipè), dates, room, total, currency, party, meal plan and eligibility are identical before and after, each re-observed by a v4 sync.
- New reservation read entirely by v4: 7e05d85c Ayres Hotel Vista Carlsbad (user 4), party 1/0/1, breakfast with its stated line, room and total read, `eligible`; three price checks succeeded.
- Syncs on this image: user 1 4 of 4 complete; user 4 4 scheduled complete plus one manual `incomplete` (preserved by policy, a pattern seen 11 times before these releases); user 3 2 complete and 1 incomplete (below). Scheduled slots: 12 completed, 0 missed. No stall notices; no extraction failures.
- Observation: user 3's scheduled sync at 2026-11-09T20:23:32Z ended `incomplete` (`agentic_inventory` path, `empty_upcoming`, 0 pages read, unseen saved reservations preserved by policy). It is that user's first incomplete sync since at least 2026-10-15; no reservation page was read, so the new reader was not involved, but "every sync completes" was not literally met. Watch user 3's next slot (planned 2026-11-10T05:17:53Z).
- Not observed: removal of personal details before TypeSafe cannot be seen in production (prompts are not stored, logs are gone); it is evidenced by tests only. No production party has children.
- Caveat, logs: daemon logs since the promotion no longer exist. Another session recreated the `booksaver` container at 2026-11-10T00:41:38Z (Docker json-file logs go with the container), so `docker logs` starts at 00:41:54Z with five clean startup lines. "No errors" rests on database outcomes (`booking_sync_runs`, `check_history`, `jev_price_runs`, `scheduled_check_slots`, `monitoring_stall_notices`) and the later promotion health logs, not on a log scan.
- Caveat, production state at read-back: at 2026-11-10T00:49Z the `booksaver` daemon was `Exited (0)`, paused at 00:46:37Z by a concurrent session's `jevprice-20261110` staging kit (its marker says its `run.sh` restores it). Not caused by this release; its restore was not observed in this read-back.

Verdict: passed, with the user 3 observation above.
