---
stage: plan
bolt: 105-jev-reads-party-meals-dates
created: 2026-11-08T18:31:21Z
---

# Implementation Plan

- `JevReservationFacts`: `header_lines` (above the room section) and `room_section_lines` (room
  section, guest row and personal lines removed) go into the state; new questions `adults`,
  `children`, `rooms`, `nights`, `meal`, `meal_line`, and date parts when code has no dates. Apply with
  agreement at 0.5; party needs nights to match the dates; room applies only for one room.
- `parse_confirmation_facts`: remove `_guest_facts` and `_meal_facts`; drop the hotel link query.
- Grouped reader: ask Jev for pages whose lifecycle is upcoming or unknown.
- Stall message names missing facts.
- Offline wording test on the eight captured real pages (kit `jevfacts-20261108`), unit tests, replay.
