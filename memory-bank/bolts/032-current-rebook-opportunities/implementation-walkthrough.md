---
stage: implement
bolt: 032-current-rebook-opportunities
created: 2026-07-27T02:16:57Z
---

## Implementation Walkthrough: Current Rebook Opportunities

### Summary

The savings repository now distinguishes historical opportunity reads from current action reads.
Telegram renders one newest action per active booking and rejects superseded selections before
worker allocation, while the shared rebook service repeats the freshness guard before creating a
session.

### Structure Overview

Persistence owns deterministic newest-row selection, user/active-booking scoping, and atomic
currentness validation plus session insertion. The application service owns the authoritative
no-session-on-stale invariant. Telegram adds an earlier user-facing check so old buttons produce
immediate guidance instead of starting background work.

### Completed Work

- [x] `src/booksaver/application/ports.py` - Defines explicit current-opportunity repository
  operations.
- [x] `src/booksaver/infrastructure/persistence/sqlite_store.py` - Selects one newest row per active
  owned booking, atomically guards session creation, and preserves historical reads.
- [x] `src/booksaver/application/rebook_service.py` - Rejects superseded or archived-booking
  opportunities before session persistence.
- [x] `src/booksaver/infrastructure/telegram/rebook_gate.py` - Uses current choices, batch-loads
  active booking labels, filters lifecycle races, and responds safely to stale commands/callbacks.
- [x] `tests/integration/test_savings_repo.py` - Covers grouping, ordering, equal-time insertion
  ties, archived filtering, and historical retention.
- [x] `tests/integration/test_rebook_repos.py` - Covers atomic stale rejection and current session
  creation.
- [x] `tests/integration/test_user_scoping.py` - Covers current-choice isolation between users.
- [x] `tests/unit/rebook/test_rebook_service.py` - Covers authoritative pre-session stale rejection.
- [x] `tests/unit/savings/test_pipeline.py` - Keeps the savings port fake aligned with the contract.
- [x] `tests/unit/telegram/test_rebook_gate.py` - Covers multi-booking picker behavior and stale
  direct/callback selections.

### Key Decisions

- **History and actionability are separate**: Existing historical list methods and rows remain
  unchanged; new operations express current-action intent.
- **SQLite insertion ID resolves timestamp ties**: The persisted order is deterministic even when
  two validations share a timestamp.
- **Layered freshness checks serve different boundaries**: Telegram improves UX before worker
  startup; the application and transactional repository guard every caller and close the
  picker-to-worker race.
- **Active booking is required**: Archived bookings cannot contribute a current rebook action.

### Deviations from Plan

None.

### Dependencies Added

None.

### Developer Notes

This policy identifies the newest stored positive opportunity. It deliberately does not perform a
live Booking.com check or expire a result after a later failed/non-saving check.
