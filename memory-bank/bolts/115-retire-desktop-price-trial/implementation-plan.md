---
stage: plan
bolt: 115-retire-desktop-price-trial
created: "2026-11-18T13:02:17Z"
---

## Implementation Plan: desktop-price-trial (retirement)

### Objective

Remove the silent desktop price trial after its evaluation (US-270, FR-6): 27 priced pairs, all
equal. Mobile web is again the only place a Booking.com price is read.

### Deliverables

- Reverse of PR #123 (merge `34d89a8`) in `src/` and `tests/`; nothing in those trees has changed
  since, so the reverse applies as one patch:
  - `daemon/desktop_trial.py` deleted; its call and constructor argument in `check_coordinator.py`.
  - `cli/commands.py`: the trial executor factory.
  - `domain/mobile_web.py`: the desktop profile, the `mobile` flag and `DesktopTrialSettings`;
    `domain/models.py` and `application/load_config.py`: the `[desktop_trial]` setting.
  - `browser_use_runtime.py`: emulation is mobile-only again.
  - `jev_page_snapshot.py`: the room-table branch and its relaxed visibility.
  - `jev_primary_executor.py`: the adapter name and session-refresh arguments.
  - `search_check_job.py`: `observe` becomes private again (only the trial called it).
  - The trial's three test files and its test in `test_jev_primary_executor.py`.
- Not reversed: the schema version. `schema.sql` loses the table, `SCHEMA_VERSION` becomes 26 and
  `_migrate_v26` drops `desktop_trial_readings`; the two delete statements for the table go.
- Tests: schema 25 with readings opens as 26 without the table and with other data intact; a
  config file with a leftover `[desktop_trial]` section loads; schema-version assertions at 26.

### Dependencies

- Bolt 114 (what is removed). Production at schema 25 with 53 rows in the table.

### Technical Approach

`git diff 34d89a8^1 34d89a8 -- src tests` applied in reverse, then the schema handled by hand as
above. Before the patch every name it removes is searched for in `src/`, `scripts/` and `tests/`
so nothing outside the patch still imports it. `jev_price_runs` rows with adapter
`jev-price-desktop-trial` stay: they are the users' recorded spend. The release backs the
database up before promotion; whether the trial image can open a schema 26 database is checked in
the implement stage.

### Acceptance Criteria

- [ ] No trial name remains in `src/`, `scripts/` or `tests/`.
- [ ] A schema 25 database with readings opens at 26 without the table; a second open is a no-op.
- [ ] A new database is at 26 without the table.
- [ ] A config with a `[desktop_trial]` section loads.
- [ ] Deleting a booking or a user works without the table.
- [ ] Full suite, ruff and mypy pass.
