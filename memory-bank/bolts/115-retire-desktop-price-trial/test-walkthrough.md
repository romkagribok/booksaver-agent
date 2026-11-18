---
stage: test
bolt: 115-retire-desktop-price-trial
created: "2026-11-18T13:07:07Z"
---

## Test Report: desktop-price-trial (retirement)

### Summary

- **Tests**: 2628/2628 passed, 1 skipped (full suite, `python3 -m pytest`); 2 new, the trial's own tests deleted
- **Lint and types**: `ruff check src tests scripts` and `mypy src` clean

### Test Files

- [x] `tests/integration/test_dom_incident_schema.py` - a schema 25 database with a reading and an index on the table opens at 26 without either, other data intact, second open a no-op
- [x] `tests/unit/test_limits_config.py` - a config with a leftover `[desktop_trial]` section loads the same as one without
- [x] Nine existing persistence tests - expected schema version 26
- [x] Deleted with the trial: `tests/unit/test_desktop_trial_config.py`, `tests/integration/test_desktop_room_table_dom.py`, `tests/unit/daemon/test_desktop_trial.py`, one test in `tests/unit/browser/test_jev_primary_executor.py`

### Acceptance Criteria Validation

- ✅ **No trial name remains in `src/`, `scripts/` or `tests/`** - searched; the only hits are the drop migration and the two new tests. `git diff 34d89a8^1 -- src scripts` shows only the schema version and migration.
- ✅ **A schema 25 database with readings opens at 26 without the table; a second open is a no-op**
- ✅ **A new database is at 26 without the table** - the existing fresh-database tests
- ✅ **A config with a `[desktop_trial]` section loads**
- ✅ **Deleting a booking or a user works without the table** - the existing delete and purge tests
- ✅ **Full suite, ruff and mypy pass**

### Issues Found

Two in the new tests themselves, fixed before the full run: the migration test first deleted the
only `schema_meta` row, which made the store treat the database as new and skip the migration;
the config test compared two configs including their load time.

### Notes

Not covered by the suite: the migration on the real production database, and a scheduled slot
running on the new image. Both are checked in staging and in the production read-back.
