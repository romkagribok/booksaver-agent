---
stage: implement
bolt: 115-retire-desktop-price-trial
created: "2026-11-18T13:07:07Z"
---

## Implementation Walkthrough: desktop-price-trial (retirement)

### Summary

The silent desktop price trial is removed. The code under `src/` is the code from before the
trial, plus schema version 26 whose migration drops the trial's table.

### Structure Overview

The trial had been written to be deleted: one module for the reading loop, one branch in the page
reader, one profile, one config section and one table. All of it came in with one merge, and
nothing else in `src/` or `tests/` has changed since, so the removal is that merge reversed.
The schema cannot be reversed, because production is at version 25 with rows in the table, so the
version moves forward and a migration drops the table.

### Completed Work

- [x] `src/booksaver/daemon/desktop_trial.py` - deleted (the reading loop)
- [x] `src/booksaver/daemon/check_coordinator.py` - no trial executor argument, no readings after a scheduled slot
- [x] `src/booksaver/cli/commands.py` - the trial executor factory removed
- [x] `src/booksaver/domain/mobile_web.py` - the desktop profile, the mobile flag and the trial settings removed; descriptor validation is Android-only again
- [x] `src/booksaver/domain/models.py`, `src/booksaver/application/load_config.py` - the `[desktop_trial]` setting removed
- [x] `src/booksaver/infrastructure/browser/browser_use_runtime.py` - emulation is always mobile again
- [x] `src/booksaver/infrastructure/browser/jev_page_snapshot.py` - the desktop room-table branch and its relaxed visibility removed
- [x] `src/booksaver/infrastructure/browser/jev_primary_executor.py` - the adapter-name and session-refresh arguments removed
- [x] `src/booksaver/monitor/search_check_job.py` - the non-recording read is private again
- [x] `src/booksaver/infrastructure/persistence/schema.sql` - the table definition removed
- [x] `src/booksaver/infrastructure/persistence/sqlite_store.py` - schema version 26, a migration that drops the table, and the two delete statements for it removed
- [x] `tests/` - the trial's three test files and its executor test deleted; one migration test and one config test added; schema-version assertions at 26

### Key Decisions

- **Reverse the merge instead of editing by hand**: afterwards `src/` differs from the tree before the trial only in the schema version and migration, which can be checked with one diff.
- **Schema 26 drops the table**: production is at 25, and a table nothing reads should not stay.
- **The trial's `jev_price_runs` rows stay**: they are each user's recorded spend, and removing them would change spend history.
- **No code for a leftover `[desktop_trial]` section**: config loading already ignores sections it does not know; a test pins that.

### Deviations from Plan

None.

### Dependencies Added

None.

### Developer Notes

The trial image cannot open a schema 26 database. Rolling this release back means restoring the
database backup taken before promotion, not only the image tag.
