---
unit: 003-conversational-booking-ops
bolt: 010-conversational-booking-ops
stage: test
status: complete
updated: 2026-07-11T19:46:16Z
---

# Test Report — Conversational Booking Ops

## Summary

| Metric | Value |
|--------|-------|
| Total tests | **504 passed, 0 failed** |
| New in this bolt | 45 |
| Pre-existing (regression surface, post Wave-1 merge) | 459 — all green |
| Lint (`ruff check src/ tests/`) | clean |
| Types (`mypy src/`) | clean (65 files) |
| Network calls in tests | none — Telegram gateway tests inject a fake transport, same pattern as bolt 008 |

## New Test Coverage by Story

### US-025 — `/register` chat dialog (24 tests)

- `tests/unit/telegram/test_register_dialog.py` (10, **new file**): full happy-path
  registration produces the same `Booking` aggregate the CLI would (property, ref-falls-
  back-to-name on skip, dates, room, price, refundability, occupancy, confirmation id);
  the final summary step shows every collected field before asking yes/no; a "no" on the
  summary aborts with nothing saved; a "no" on refundability aborts with the
  CLI-identical `BookingRejectedError` wording; an invalid check-out (before check-in)
  re-prompts with the real `StayDates` domain message; a bad occupancy answer (0 adults)
  re-prompts with the real `Occupancy` domain message; an unrecognized sender can't even
  start the dialog; the per-user booking cap blocks at dialog start; the cap is
  re-checked (and blocks) at save time even if it wasn't breached at start (race
  defense); the owner is exempt from the cap.
- `tests/unit/telegram/test_dialogs.py` (+4): `validate` receives the answers collected
  so far (cross-field rule); a `prompt` may be a callable rendered from those answers;
  `DialogAborted` ends the dialog with its message and clears the active state, both from
  a later step and from the very first step.
- `tests/unit/telegram/test_commands_readonly.py` (+4): `/bookings` shows only the
  calling user's own bookings (two users, two bookings, cross-checked both directions);
  an unrecognized sender gets a polite refusal on `/bookings` and on `/savings`;
  `/checks` on another user's booking id returns the identical "not found" message as a
  genuinely unknown id (no oracle for probing other users' ids).
- `tests/unit/telegram/test_gateway.py` (+2 of the file's +3 relevant to US-025): a full
  `/register` conversation driven through the real `BotLoop` + scripted Telegram
  transport ends in a "Registered:" reply and shows the summary prompt; `/cancelflow`
  mid-dialog aborts a `/register` in progress through the same bot loop.

### US-030 — Route savings alerts to the booking owner (5 tests)

- `tests/unit/notifications/test_routing.py` (5, **new file**, **new test package**):
  an owner-owned booking uses the static owner notifier list unchanged; an
  invited-user-owned booking routes to a fresh `TelegramNotifier` addressed to that
  user's own chat; a user with no linked Telegram id and no reachable chat yields no
  notifiers rather than crashing; a revoked owning user yields no notifiers; a booking
  with no resolvable owner (orphaned) yields no notifiers.
- `tests/unit/savings/test_pipeline.py`: unchanged and still green — `NotificationDispatcher`'s
  new `resolver` argument is additive; every existing test constructs it with the old
  positional `notifiers` list.

### US-031 — Per-user cost caps and abuse limits (16 tests)

- `tests/unit/test_limits_config.py` (7, **new file**): `[limits]` defaults when the
  section is absent; overriding all four fields parses; zero/negative values rejected at
  `load_config` with a `limits:`-prefixed error; a non-numeric value rejected; the
  `LimitsSettings` value object itself rejects any field `< 1` (parametrized across all
  four fields) and accepts its defaults.
- `tests/unit/monitor/test_user_limits.py` (12, **new file**): `DailyCounter` increments,
  keys are independent, rolls over at UTC midnight, and its `snapshot()` reflects the
  current day; `build_check_plan` interleaves bookings round-robin across users (not
  concatenated per-user), excludes a user already at today's cap and reports them,
  silently skips users with no bookings, and produces an empty plan for no users;
  `users_needing_capped_notice` reports a capped user once, not again on a same-day
  repeat tick, again the next day, and reports nothing when no one is capped.
- `tests/unit/telegram/test_gateway.py` (+1 of the file's +3): a per-chat message rate
  limit (`messages_per_minute_per_chat=1`) drops the second reply within the same window
  rather than sending or queuing it.

## Regression Verification

- Full pre-existing suite (459 tests as of the `phase-3-telegram-interface` Wave-1 merge,
  commit `98a0094`) passes unchanged.
- `tests/unit/monitor/fakes.py`'s `FakeBookingRepository` gained `get_owner_user_id` and
  owner-tracking on `add()`/`list_active_for_user`/`list_all_for_user` — audited every
  existing call site (`test_check_job.py`, `test_search_check_job.py`,
  `test_monitor_agent_wiring.py`, `test_pipeline.py`, `test_rebook_service.py`); none call
  the now-scoped methods, so behavior is unchanged for all of them.
- `BookingComSearchMonitor.run_all_active()`'s new `bookings` parameter defaults to `None`
  (falls back to `self._bookings.list_active()`, the pre-existing behavior) — every
  existing caller in `test_check_job.py`/`test_search_check_job.py` calls it with no
  arguments and is unaffected.
- `NotificationDispatcher.__init__`'s `notifiers` parameter is now optional
  (`list[Notifier] | None = None`) with `resolver` as an alternative; every existing test
  and the pre-bolt call site in `cli/commands.py` used the positional-list form and
  continue to.

## Gates

- `python3 -m ruff check src/ tests/` — clean
- `python3 -m mypy src/` — clean (65 source files)
- `PYTHONPATH=src python3 -m pytest` — 504 passed, 0 failed, 0 skipped
