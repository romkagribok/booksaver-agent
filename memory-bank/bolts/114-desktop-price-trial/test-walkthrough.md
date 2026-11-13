---
stage: test
bolt: 114-desktop-price-trial
created: "2026-11-13T03:13:38Z"
---

## Test Report: desktop-price-trial

### Summary

- **Tests**: 2655/2655 passed, 1 skipped (full suite, `python3 -m pytest`); 39 new
- **Lint and types**: `ruff check src tests` and `mypy src` clean

### Test Files

- [x] `tests/unit/test_desktop_trial_config.py` - desktop profile options, each profile rejects the other kind of descriptor, config cannot select the desktop profile, `[desktop_trial]` parsing and rejection
- [x] `tests/integration/test_desktop_room_table_dom.py` - the reader in a real browser DOM: room table read as rooms and rates, totals ground to the whole-stay price, rate cards read as before even beside a table
- [x] `tests/unit/daemon/test_desktop_trial.py` - one stored reading per checked booking and no other table written, session never refreshed, stop at sign-out or bot wall, budget refusal stored, no reading without a session or while stopping, a raising reading does not reach the slot, slot hook only for trial users before the end date and after all checks, deletion with booking or user, trial executor wiring, emulation follows the profile
- [x] `tests/unit/browser/test_jev_primary_executor.py` - a run is recorded under its adapter name
- [x] Seven existing migration tests - expected schema version 25

### Acceptance Criteria Validation

- ✅ **Desktop profile options accepted as non-mobile; config cannot select it; mobile validation unchanged**
- ✅ **Room table read as rooms with rates, without selector or paid-breakfast amounts, without rows for fewer guests**
- ✅ **Mobile card reading unchanged**
- ✅ **One stored reading per checked booking for a trial user before `ends_on`; none otherwise**
- ✅ **History, traces, savings, counters and the saved session untouched by a reading**
- ✅ **A raising reading is logged and the slot completes; sign-out or bot wall stops the slot's readings**
- ✅ **`user_ids` without `ends_on` is rejected**
- ✅ **Readings deleted with their booking or user**
- ✅ **ruff, mypy and the full suite pass**

### Issues Found

None in the suite. Codex review of `bf53372` found two: a rate's capacity was compared with the
adults only (P1), and a bot wall on a later mobile check did not prevent readings for earlier
bookings (P2). Both fixed with a test each.

### Notes

Not covered by automated tests, because they need Booking.com and a real session: that a
signed-in desktop page uses the same room table, that Jev's answers on desktop rows verify a
price, and that the session stays valid after a desktop reading. These are the live qualification
steps of the release.
