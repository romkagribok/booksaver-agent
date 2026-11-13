---
stage: implement
bolt: 114-desktop-price-trial
created: "2026-11-13T03:13:38Z"
---

## Implementation Walkthrough: desktop-price-trial

### Summary

A code-owned desktop Chromium profile, a desktop room-table branch in the page reader, and a
silent desktop reading that runs after a scheduled slot's normal checks for the users named in
`[desktop_trial]`. Each reading is stored beside its mobile check; nothing else is written.

### Structure Overview

The trial reuses the Jev price executor, the validators and the offer selection unchanged. Only
three things are new: the profile the browser runs with, how the reader finds rooms and rates on
the desktop page, and one loop that runs readings and stores them. The loop lives in its own
module so the trial can be deleted without touching the check path.

### Completed Work

- [x] `src/booksaver/domain/mobile_web.py` - desktop trial profile, profile-aware descriptor validation, config can only select mobile profiles, `DesktopTrialSettings`
- [x] `src/booksaver/infrastructure/browser/browser_use_runtime.py` - mobile, touch, orientation and platform emulation follow the profile
- [x] `src/booksaver/infrastructure/browser/jev_page_snapshot.py` - room-table branch: room from the spanning cell, one rate per row, price read through the hidden-from-screen-reader wrapper, amounts only from the price cell, rows for fewer guests skipped
- [x] `src/booksaver/infrastructure/browser/jev_primary_executor.py` - optional adapter name and session-refresh switch
- [x] `src/booksaver/monitor/search_check_job.py` - public `observe` that neither records history nor tracks failures
- [x] `src/booksaver/daemon/desktop_trial.py` - the reading loop and its stop conditions
- [x] `src/booksaver/daemon/check_coordinator.py` - collects the slot's checked bookings and calls the loop after them
- [x] `src/booksaver/infrastructure/persistence/schema.sql`, `sqlite_store.py` - `desktop_trial_readings` (schema 25), deleted with its booking or user
- [x] `src/booksaver/application/load_config.py`, `src/booksaver/domain/models.py` - `[desktop_trial] user_ids`, `ends_on`
- [x] `src/booksaver/cli/commands.py` - trial executor factory: desktop profile, no session refresh, own adapter name, half the daily cap

### Key Decisions

- **Readings after the slot's checks**: a slot has one time allowance for all of a user's bookings; a reading inside it could make a later real check run out of time.
- **Amounts only from the price cell**: the desktop row also shows a paid-breakfast price and a room-count selector with prices; as candidate totals they would make every such rate ambiguous. Grounding itself is unchanged.
- **Reading through the hidden-from-screen-reader wrapper, table only**: Booking.com's desktop table puts both the displayed price and its accessible label inside that wrapper; the mobile cards do not, so card reading keeps the stricter rule.
- **Half the daily cap**: a trial reading can never use the spend the user's real checks need.

### Deviations from Plan

None.

### Dependencies Added

None.

### Developer Notes

The room-table branch keys on `#hprt-table` and Booking.com's cell classes (marked as a shortcut
in the code). Public desktop pages from this machine showed the same totals as mobile for one
hotel; that is one logged-out sample, not evidence about signed-in prices. Signed-in behaviour
and session reuse are qualified on the VPS in the operations phase.
