---
id: 002-silent-desktop-readings
unit: 001-desktop-price-trial
intent: 041-desktop-price-trial
status: draft
priority: must
created: "2026-11-13T03:02:27Z"
assigned_bolt: 114-desktop-price-trial
implemented: false
---

# Story: US-269 Trial users get a silent desktop reading after each scheduled slot

## User Story

**As the** owner
**I want** a desktop reading stored beside each scheduled mobile check of a trial user, with nothing shown to that user
**So that** after a week I can see whether desktop prices are ever cheaper

## Acceptance Criteria

- [ ] **Given** user 4 in `[desktop_trial] user_ids` and today before `ends_on`, **When** a scheduled slot has checked two bookings, **Then** two readings are stored, each with the mobile check's id, outcome, price and currency or failure reason.
- [ ] **Given** a user not in `user_ids`, or today on or after `ends_on`, **When** a slot runs, **Then** no reading is taken.
- [ ] **Given** a trial slot, **When** it completes, **Then** check history, traces, savings, alerts and the daily check counter are the same as without the trial, and the saved session is not written by a reading.
- [ ] **Given** a reading that raises or times out, **When** the slot continues, **Then** the error is logged and the slot completes normally.
- [ ] **Given** a reading that ends signed out or at a bot wall, **When** more bookings remain, **Then** the slot takes no further readings.
- [ ] **Given** the user's Jev spend today is over half the daily cap, **When** a reading starts, **Then** it is refused and stored as a budget failure.
- [ ] **Given** `user_ids` without `ends_on`, **When** config loads, **Then** it is rejected.
- [ ] **Given** a trial user's booking or account is deleted, **When** the delete runs, **Then** their readings are deleted.

## Technical Notes

`daemon/desktop_trial.py` (the reading loop), a call at the end of the scheduled user slot,
`desktop_trial_readings` (schema 25, additive), `[desktop_trial]` config, the Jev primary executor
with the desktop profile, no session refresh, adapter `jev-price-desktop-trial` and half the cap.

## Dependencies

### Requires
- US-268

### Enables
- The FR-5 evaluation

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| The mobile check ended `auth_required` | No reading for that booking |
| The daemon is stopping | Remaining readings are skipped |
| The session is not ready when readings start | No readings |

## Out of Scope

- `/checknow`, alerts or results from a desktop price, a report command.
