---
id: 003-retire-the-trial
unit: 001-desktop-price-trial
intent: 041-desktop-price-trial
status: draft
priority: must
created: "2026-11-18T13:00:53Z"
assigned_bolt: 115-retire-desktop-price-trial
implemented: false
---

# Story: US-270 The desktop price trial is removed

## User Story

**As the** owner
**I want** the desktop price trial taken out once it has shown that desktop prices do not differ
**So that** the product carries no experiment code, no extra page loads and no unused table

## Acceptance Criteria

- [ ] **Given** the repository, **When** it is searched for the trial (the desktop profile, the room-table reader, the reading loop, the trial executor, `[desktop_trial]`), **Then** nothing remains outside the memory bank.
- [ ] **Given** a database at schema 25 with trial readings, **When** the store opens, **Then** it is at schema 26 and `desktop_trial_readings` does not exist; every other table is unchanged.
- [ ] **Given** a new database, **When** the store opens, **Then** it is at schema 26 without the table.
- [ ] **Given** a config file that still has a `[desktop_trial]` section, **When** config loads, **Then** it loads and the section has no effect.
- [ ] **Given** a scheduled slot, **When** it completes, **Then** it takes no desktop reading and its checks, history and alerts are as before the trial.
- [ ] **Given** a booking or a user is deleted, **When** the delete runs, **Then** it succeeds without the table.

## Technical Notes

Reverse of PR #123 in `src/` and `tests/`, except the schema: version 26 with a migration that
drops the table, since production is at 25. `jev_price_runs` rows with adapter
`jev-price-desktop-trial` stay as spend history.

## Dependencies

### Requires
- The FR-5 evaluation and the owner's decision (2026-11-17)

### Enables
- Closing GitHub issue #7

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| The release is rolled back to the trial image after the table is dropped | The trial image opens the schema 26 database and recreates the table empty (checked with both trees on one database); the 53 readings are gone unless the backup is restored. If the removal is promoted again the empty table stays and is dropped by hand |
| Production config still has the section when the new image starts | Ignored; the promotion removes it |

## Out of Scope

- The rest of issue #7 (dual-channel selection, alerts, provenance, concurrency): closed with the issue.
