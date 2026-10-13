---
version: bookedtotal-baf9b29
commit: baf9b29
created: "2026-10-12T22:25:30Z"
status: deployed-verified
recorded: "2026-10-12T22:26:23Z"
---

# Confirmation booked total — released and verified

Intent 023, unit 013, bolt 092 (ADR-058), stories US-226 to US-228. Account synchronization now
records the booked total in the currency the confirmation page prints, reads the refund schedule
layout, and lets a total reconciled on the confirmation page replace a stale saved total. No
schema, configuration or dependency change.

## Artifact and verification

- Source `baf9b29` (PR #82); merge `8a3eb1ed89f2e2dd065e04923a9eb6384afc0a0d`, `src` identical
  to the reviewed head.
- Image `booksaver-agent:bookedtotal-baf9b29` =
  `sha256:0f81986a3c2c280c84959cfbe1c4fef4ee580d453ac69e3947abc8ef50649e12`, built on
  `mealplan-d19f7b5` from `git archive baf9b29` (archive sha256 `a7bf7dd4…02aa25`).
- Quality: 3,257 tests, one skip; Ruff and mypy (133 modules) clean; AI-DLC validators 0 errors,
  0 status inconsistencies. Coverage not measured.
- Bugbot: **passed** on head `baf9b29` (`scripts/bugbot_merge_gate.py 82` printed `passed`, no
  Cursor threads).
- Dev on the exact image, `--network none`: 133 installed modules match source, pins matched,
  `pip check`, daemon and Chromium smoke, three supervisor cleanup cases, and a synthetic
  dollar-layout read.
- Staging, offline: `sqlite3.backup` production snapshot, `--network none`; schema 21 before and
  after, integrity ok, zero foreign-key violations, row counts unchanged. Snapshot deleted.
- Staging, live: the affected caller's normal inventory refresh on cloned state with the data
  volume read-only and Telegram delivery disabled, production paused 2026-10-12T22:21:42Z to
  22:23:26Z. Refresh complete, 1 discovered, 1 eligible, no unknown facts; saved USD301 became
  USD346.08 on the reservation and the same monitoring booking, its 92 checks kept, refund
  deadline 2026-11-21; other callers' 12 rows identical. Production restored on its previous
  image, healthy.
- Production: promoted 2026-10-12T22:25:30Z with backup
  `/opt/booksaver-backups/bookedtotal-baf9b29-20261012` (archive checksum verified) and rollback
  tag `booksaver-agent:rollback-pre-bookedtotal-baf9b29`; healthy, zero restarts, OOM false, no
  published ports, Caddy unchanged, SQLite integrity and foreign keys ok, schema 21, public
  health 200, no error or traceback in the first start-up log, installed reader and marker
  present. Configuration unchanged.

## Earlier replay candidates

Before the commit, four isolated replays ran from uncommitted source (`bookedtotal-wip-9a45af6`,
`bookedtotal-wip-0478f4c`) between 22:00Z and 22:17Z. The second and third showed that the real
dollar page prints `US$` amounts and closes the total with "Additional Info" instead of a
final-price statement; the reader was corrected and the fourth passed. Those images are not the
release image. Across all five pauses production was stopped for about seven minutes; no
scheduled check was due. The third replay's log holds about sixteen captured lines of the owner's
own price block and is kept root-only in the kit.

## Operations checkpoints

The owner's instruction "commit and push and merge so this is present in production"
(2026-10-12, after reviewing the replay result) was taken as approval of the build, staging and
production steps. No separate monitoring step was added; the existing content-free coverage
diagnostic now also counts `unknown_facts`. Recent releases record operations in this file and
the unit's construction log rather than a per-unit deployment folder; this release does the same.

## Concurrent work

PR #78 and PR #77 took bolts 089–091, US-216 to US-225, ADR-056 and ADR-057 and schema v20 and
v21 first; this work was rebased and renumbered to bolt 092, US-226 to US-228 and ADR-058. No
other pull request was open at merge or at promotion.

## Observed (2026-10-13T14:06:46Z)

Read-only from the production database after the scheduled synchronization of
2026-10-13T02:03Z: the owner's reservation reads USD 346.08 with refund deadline 2026-11-21, as
expected (USD 301 at promotion), and its monitored booking carries the same total. The invitee's
two unmonitored reservations are still not eligible: one for `missing_booked_total`, one for
`refundability_unknown`. This release did not fix them; no work is planned for them here.

## Pending (at release; item 1 is answered above, item 2 is not pursued)

1. Read the owner's reservation after the first production synchronization following
   2026-10-12T22:25:30Z (next scheduled for that caller: 2026-10-13T02:03Z, or any `/bookings`).
   Expected: USD346.08 and refund deadline 2026-11-21. At promotion it still read USD301.
2. Read `unknown_facts` for the invitee's two unmonitored reservations to learn which rule stops
   them, if this release does not already fix them.
3. Remove the two work-in-progress images and the kit's captured-lines log when no longer needed.

Rollback: `docker tag booksaver-agent:rollback-pre-bookedtotal-baf9b29 booksaver-agent:latest`
and recreate. The previous image runs on the same schema; a baseline already corrected to the
confirmation total stays correct. Evidence: `/opt/booksaver-releases/bookedtotal-20261012/`.
