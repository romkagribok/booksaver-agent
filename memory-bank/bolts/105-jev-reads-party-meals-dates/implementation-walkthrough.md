---
stage: implement
bolt: 105-jev-reads-party-meals-dates
created: 2026-11-08T18:45:20Z
---

# Implementation Walkthrough

- `JevReservationFacts` (adapter v4) adds, in the same two calls: `adults`, `children`, `rooms`,
  `nights` over `header_lines` (lines above the room section); `meal` (six classes) and
  `meal_line` over `room_section_lines` (room section to the price, the line after a bare "Guest
  name" dropped); and date parts only when code read no dates. Every answer needs agreement at 0.5;
  `check_party` needs all four counts and nights equal to the dates; `check_dates` needs real dates,
  1 to 90 nights, and derives the lifecycle; the refund check runs after Jev's dates. The room type
  now applies only when the party is one room. `_PERSONAL` also drops phone numbers and guest-name
  rows.
- `parse_confirmation_facts`: `_guest_facts`, `_meal_facts` and their word lists removed; a hotel
  link's query and fragment are dropped instead of losing the property.
- Grouped reader: Jev reads pages whose lifecycle is upcoming or unknown.
- Stall message names the missing facts ("booked total or room type").
- Unit tests found `not_stated` crashing the number reader (it starts with "n"); fixed.
