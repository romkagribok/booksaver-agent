---
version: noavail-39a666b
commit: 39a666b
created: "2026-11-06T17:25:14Z"
status: deployed-verified
recorded: "2026-11-10T00:52:50Z"
---

# No availability for the dates is a conclusive result (intent 032)

## Change

Bolt 103 (US-255): when Jev names no room type, Jev is asked once whether the page offers the whole
requested stay, but only after the page passes the property, stay and party checks now shared with
price validation (`query_identity_rejection`). A confident "unavailable" (at least 0.8) is recorded as
`no_equivalent_offer` with the detail "The property shows no availability for these dates."

## Artifact and verification

- PR #105, head `ff96ef6`, merge `39a666b2ff7f`. Codex found one P2 on `945d676` (unavailability
  declared without query identity); fixed in `ff96ef6`, which Codex reviewed with no major issues.
- Merge gate: `scripts/codex_merge_gate.py 105` reported the fixed finding's thread as unresolved;
  the merge command ran anyway because the gate's exit status was hidden by a pipe. The thread was
  resolved right after the merge; the gate cannot be re-run on a merged PR. The finding was fixed
  and re-reviewed clean before the merge.
- Image `booksaver-agent:noavail-39a666b` =
  `sha256:d9a54fb48a3a14461c12bd71d85ac12260c024d37b85f8e97baba109515ff619`, built from the merge's
  `git archive` on `releaseb-58e2113` with the clean-tree kit Dockerfile; 116 modules.
- Quality: 2,610 passed, 1 skipped; Ruff and mypy clean; AI-DLC validators 0 errors.
- Live replay on cloned data (kit `noavail-20261106`, daemon paused and restored healthy three
  times, last at 17:20:08Z): Kalipè (2c711962) `no_equivalent_offer`, Jev "unavailable" 0.91;
  AIRINN (032be4a7) unchanged, room_mismatch=26.
- Promotion: backup `/opt/booksaver-backups/noavail-39a666b-20261106`, healthy, schema 24, public
  health passed, Caddy unchanged, at 2026-11-06T17:25:14Z. Rollback tag
  `booksaver-agent:rollback-pre-noavail-39a666b` (no schema change).

## Production read-back

Read 2026-11-10T00:46:02Z to 00:49:37Z. Method: read-only, through the specs.md operations agent's verify step: `ssh booksaver`, `docker ps/inspect/events/logs`, and the live database opened read-only from the host volume (`mode=ro`); the app's store was not opened and nothing was stopped, restarted, written or replayed.

- Kalipè (2c711962, Residence Kalipè, user 4): the awaited scheduled sync ran at 2026-11-06T23:52:16Z and the check at 23:53:34Z recorded `no_equivalent_offer`, "The property shows no availability for these dates." (Jev `unavailable`, 17 calls, about USD 0.00035). Same result on 8 consecutive checks to 2026-11-09T10:02:28Z across three images; the ninth hit user 4's daily check limit.
- No stall notice for this booking, or for any booking, since 2026-11-06.
- Control: AIRINN (032be4a7) unchanged, `no_equivalent_offer` room_mismatch=26 on this image.
- Not observed: the availability confidence (0.91 on staging) is not stored in production; the 0.8 floor is implied by the `unavailable` status only.
- Caveat, logs: daemon logs since the promotion no longer exist. Another session recreated the `booksaver` container at 2026-11-10T00:41:38Z (Docker json-file logs go with the container), so `docker logs` starts at 00:41:54Z with five clean startup lines. "No errors" rests on database outcomes (`booking_sync_runs`, `check_history`, `jev_price_runs`, `scheduled_check_slots`, `monitoring_stall_notices`) and the later promotion health logs, not on a log scan.
- Caveat, production state at read-back: at 2026-11-10T00:49Z the `booksaver` daemon was `Exited (0)`, paused at 00:46:37Z by a concurrent session's `jevprice-20261110` staging kit (its marker says its `run.sh` restores it). Not caused by this release; its restore was not observed in this read-back.

Verdict: passed.
