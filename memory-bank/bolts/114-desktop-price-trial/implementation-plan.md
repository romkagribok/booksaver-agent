---
stage: plan
bolt: 114-desktop-price-trial
created: "2026-11-13T03:04:25Z"
---

## Implementation Plan: desktop-price-trial

### Objective

A silent desktop price reading beside each scheduled mobile check of a trial user, stored as a
pair, with nothing the user can see (US-268, US-269).

### Deliverables

- `domain/mobile_web.py`: a desktop trial profile (Playwright "Desktop Chrome") that validates as
  non-mobile and that `MobileWebSettings.from_values` refuses; `DesktopTrialSettings`
  (`user_ids`, `ends_on`, `active_for`).
- `browser_use_runtime.py`: mobile, touch, orientation and platform emulation follow the profile.
- `jev_page_snapshot.py`: a room-table branch used only when no rate card exists and the desktop
  room table does.
- `jev_primary_executor.py`: optional adapter name and session-refresh switch (defaults unchanged).
- `daemon/desktop_trial.py`: the reading loop; `check_coordinator.py`: one call at the end of the
  scheduled user slot; `search_check_job.py`: a public non-recording `observe`.
- `schema.sql` + schema 25: `desktop_trial_readings`; deleted with its booking or user.
- `load_config.py`, `domain/models.py`, `cli/commands.py`: `[desktop_trial]` and the trial
  executor factory.
- Tests for each acceptance criterion.

### Dependencies

- Playwright's "Desktop Chrome" device descriptor: the desktop identity.
- The existing Jev runtime, validators and offer selection: reused unchanged.

### Technical Approach

The trial executor is the existing Jev primary executor built with the desktop profile, no session
refresh, its own adapter name, and half the daily cap, so spend is recorded and capped by the code
that already does it. Readings run at the end of `_run_scheduled_user_locked`, after every normal
check of the slot, each on its own 120-second limit, so the slot's shared time allowance is not
touched. Each reading builds a `BookingComSearchMonitor` without a trace repository and calls
`observe`, which neither records history nor tracks failures; the resulting outcome, price, room
and failure reason go into `desktop_trial_readings` under the mobile check's id. The loop stops at
a sign-out, a bot wall, a daemon stop or a deactivated user, and catches everything.

Shortcut: the room-table branch keys on Booking.com's `#hprt-table` and its cell classes; upgrade
to a structural rule if the trial is kept.

### Acceptance Criteria

- [ ] Desktop profile options accepted as non-mobile; config cannot select it; mobile validation unchanged.
- [ ] Room table read as rooms with their rates, price and cancellation lines, without selector or paid-breakfast amounts, without rows for fewer guests.
- [ ] Mobile card reading unchanged.
- [ ] One stored reading per checked booking for a trial user before `ends_on`; none otherwise.
- [ ] History, traces, savings, alerts, counters and the saved session untouched by a reading.
- [ ] A raising reading is logged and the slot completes; sign-out or bot wall stops the slot's readings.
- [ ] `user_ids` without `ends_on` is rejected.
- [ ] Readings deleted with their booking or user.
- [ ] ruff, mypy and the full suite pass.
