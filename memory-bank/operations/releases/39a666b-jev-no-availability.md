---
version: noavail-39a666b
commit: 39a666b
created: "2026-11-06T17:25:14Z"
status: deployed-verified
recorded: "2026-11-06T17:30:00Z"
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

The dad's scheduled run at 2026-11-06T23:53Z recorded Residence Kalipè as a conclusive
`no_equivalent_offer` with "The property shows no availability for these dates." Eight checks to
2026-11-09T10:02Z gave the same result, with no stall notice for it.
