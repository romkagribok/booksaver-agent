---
stage: plan
bolt: 104-jev-reads-room-type
created: 2026-11-08T02:21:32Z
---

# Implementation Plan

- `JevReservationFacts.__call__`: when the code facts show one room, add a `room` choice question
  over the page's short lines (bounded); apply it when both calls agree at 0.5 or more.
- `_agreed(results, "total", 0.0)`: agreement plus `check_total` is the guard.
- `parse_confirmation_facts`: delete `_room_fact`; gate `_meal_facts` on the single-room party.
- `search_check_job`: room-mismatch detail becomes "No matching room type found ...".
- Tests; staging replay of the dad's sync comparing every stored room type before and after.
