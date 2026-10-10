---
version: mealplan-d19f7b5
commit: d19f7b5
created: "2026-10-10T08:15:02Z"
status: deployed-awaiting-readings
recorded: "2026-10-10T08:17:33Z"
---

# Reservation meal plan — released, production readings pending

Intent 027, bolt 090 (ADR-057), stories US-220 and US-221. Account synchronization now records
each reservation's meal plan and `/bookings` shows it. **Offer selection and alerts are
unchanged**: a cheaper offer with fewer meals is still reported until bolt 091 ships.

## Artifact and verification

- Source `d19f7b5` (PR #77, final head `509a000`, records only after `d19f7b5`); merge
  `063c3e430e71ef5dd9c9ebd7b0e175ad7c5bf9f7` at 2026-10-10T08:14:34Z, `src` identical to source.
- Image `booksaver-agent:mealplan-d19f7b5` =
  `sha256:3c6438561e70e46e07fa5db48fa2f46380f477f5ef9a93d4eb3c6a19de26302c`, built on
  `jevprimary-7b18adc`.
- Quality: 3,226 tests, one skip; Ruff and mypy (133 modules) clean; AI-DLC validators 0 errors,
  0 status inconsistencies. Coverage not measured.
- Bugbot: **passed** on head `509a000` (`scripts/bugbot_merge_gate.py 77` printed `passed`, three
  resolved Cursor threads). It reported three issues on earlier heads, all fixed with regressions:
  a facilities list read as the booked meal plan; "exclusive" read as a denial; a bare digit read
  as a price.
- Dev on the exact image, `--network none`: 133 installed modules match source, pins matched,
  `pip check`, daemon and Chromium smoke, three supervisor cleanup cases, CLI help.
- Staging: `mealplan_stage_probe.py` on a `sqlite3.backup` production snapshot, `--network none`.
  v20 to v21 migration with integrity ok and zero foreign-key violations before and after; row
  counts preserved (3 users, 5 bookings, 13 reservations, 230 history rows, 31 opportunities, 82
  comparisons); every existing meal plan unknown; `/bookings` rendered five entries with five meal
  lines for three users; one existing reservation received a stated meal plan with its booking and
  opportunities kept. `STAGE PASS`. Snapshot deleted.
- Production: promoted 2026-10-10T08:15:02Z with backup `/opt/booksaver-backups/mealplan-d19f7b5-20261010`
  (archive checksum verified) and rollback tag `booksaver-agent:rollback-pre-mealplan-d19f7b5`;
  healthy, zero restarts, OOM false, no published ports, Caddy unchanged, SQLite integrity and
  foreign keys ok, schema 21, the three new columns present, public health 200. Configuration
  unchanged: `browser_use` price method with the paired Jev comparison on.

## Startup defect found in production

At the first scheduler pass after the restart, `booking_com_check` and
`booking_com_session_maintenance` each failed once with
`sqlite3.OperationalError: duplicate column name` raised from `_migrate_v21`. The daemon opens the
database from several threads at start; each saw schema 20, each checked that the column was
missing, and all but one lost the race to add it. Effect: both jobs skipped that one pass and ran
normally on the next (60 seconds later); no check slot was consumed, no data was lost, schema 21
was recorded once, and the heartbeat never went stale. The single-connection staging probe could
not show this.

The same concurrent start left two `schema_meta` rows for v20 at the previous release; that
migration only created a table, so nothing failed then.

Not fixed in this image. The migration cannot run again on this database, so production is not
exposed; another installation upgrading from v20 would see the same one-pass failure. The fix
(tolerate a column another connection has just added) is proposed to the owner and belongs to
bolt 090, whose test stage stays open.

## Operations checkpoints

The owner's instructions "proceed to implement, merge and redeploy" (2026-10-10T01:49:45Z) and
"finalize this and merge ... merge and redeploy" (2026-10-10T08:07:38Z) were taken as approval of
the build, staging and production steps. Build and staging were run before the second
instruction. No separate monitoring step was added.

## Concurrent work

PR #78 took schema v20, bolt 089, US-216 to US-219 and ADR-056 first; this release was rebased
and renumbered to v21, bolts 090 and 091, US-220 to US-225 and ADR-057. A third session
(confirmation-page booked total) waits for this release's read-back before it pauses the daemon,
and starts at bolt 092, US-226 and ADR-058.

## Pending

1. Read the meal plans recorded by the first synchronizations after 2026-10-10T08:15:02Z (next scheduled:
   user 4 at 09:51Z, user 3 at 14:48Z, user 1 at 15:38Z, or any `/bookings`). Confirm that a
   reservation with breakfast reads `breakfast`; if it reads `unknown`, add the stored wording to
   the classifier.
2. Decide and ship the startup-race fix.
3. Complete bolt 090 with `bolt-complete.cjs` after 1.
4. Bolt 091 (the gate and the alert wording).

Rollback: `docker tag booksaver-agent:rollback-pre-mealplan-d19f7b5 booksaver-agent:latest` and
recreate. The previous image runs on the migrated database; the added columns are nullable or
defaulted. Evidence: `/opt/booksaver-releases/mealplan-20261010/` (build, dev, stage and promotion
logs for every candidate).
