---
stage: test
bolt: 089-reservation-meal-plan
created: "2026-10-10T02:02:11Z"
status: in-progress
---

# Reservation meal plan verification

Evidence appended as recorded.

## 2026-10-10T02:02:11Z — construction evidence

Commands: `python3 -m ruff check src tests` (clean), `python3 -m mypy src` (no issues in 132
source files), `python3 -m pytest` (3,151 passed, 1 skipped).

- US-216, `Meal Plan` row: the owner's real desktop example ("No meal is included in this room
  rate.") reads `none` with its wording; inline, next-line and colon forms read the included
  value; priced-extra wording reads `none`; unrecognized wording and unranked combinations read
  `unknown` (`tests/unit/test_inventory_confirmation_facts.py`, `tests/unit/test_meal_plan.py`).
- US-216, missing row: `none` with no text when the room and guest row were read; `unknown`
  without the guest row or the room heading; meal wording outside the section is ignored.
- US-216, trust: the meal plan reaches the observed reservation only from the parser payload
  (`tests/unit/test_grouped_inventory_runtime.py`); duplicate readings merge without guessing
  (`tests/unit/test_inventory_executor.py`).
- US-216, storage: value and text are stored and projected to the booking; an existing
  reservation receives its meal plan on the next synchronization on both the agentic and the
  legacy path; `unknown` and a silent reading never replace a stated value; a v19 database
  migrates to v20 with every meal plan `unknown`; recording a meal plan keeps a saved opportunity
  (`tests/integration/test_account_sync_persistence.py`).
- US-217: `/bookings` shows the meal plan line for included, none and unknown
  (`tests/unit/telegram/test_commands_readonly.py`).

Not yet evidenced: the desktop wording of an included breakfast on a real reservation, and
readings on production reservations. Both are recorded at release.
