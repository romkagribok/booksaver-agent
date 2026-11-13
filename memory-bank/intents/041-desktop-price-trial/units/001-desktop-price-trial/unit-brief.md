---
unit: 001-desktop-price-trial
intent: 041-desktop-price-trial
phase: construction
status: in-progress
unit_type: backend
default_bolt_type: simple-construction-bolt
created: "2026-11-13T03:02:27Z"
updated: "2026-11-13T03:02:27Z"
---

# Unit Brief: Desktop price trial

## Purpose

Take a silent desktop price reading beside the mobile check for trial users, so the owner can
decide whether issue #7 is worth building.

## Scope

### In Scope
- Desktop Chromium profile for the Jev browser host; desktop room-table reading.
- Readings after a scheduled slot for `[desktop_trial] user_ids` until `ends_on`; storage.

### Out of Scope
- Using a desktop price for results, savings or alerts; `/checknow`; parallel browsers; a report
  command; anything shown to a user. These are the rest of issue #7.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Desktop browser profile | Must |
| FR-2 | Read the desktop room table | Must |
| FR-3 | Silent desktop reading after a scheduled slot | Must |
| FR-4 | The trial changes nothing the user can see or rely on | Must |

## Stories

| Story | Title | Priority | Bolt |
|-------|-------|----------|------|
| US-268 | A desktop profile reads a Booking.com price | Must | 114-desktop-price-trial |
| US-269 | Trial users get a silent desktop reading after each scheduled slot | Must | 114-desktop-price-trial |

## Data Storage

| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| `desktop_trial_readings` | SQLite | About 15 rows a day for user 4 | Until the trial is retired; deleted with the booking or user |

## Success Criteria

- [ ] A trial slot stores one reading per checked booking and changes nothing else.
- [ ] Mobile reading and checks behave as before (existing suite green).
- [ ] Live qualification: a signed-in desktop reading verifies a price and the session stays valid.
